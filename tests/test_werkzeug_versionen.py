"""Die ruff-Version steht an genau einer Stelle — und bleibt dort.

Sie stand an zweien: `ruff==0.16.1` im `[dev]`-Extra und noch einmal als
`pip install ruff==0.16.1` in `ci.yml`. Beide nannten dieselbe Version, der
Aufbau war also nicht rot — aber der CI-Schritt lief nach dem Install des
Extras und gewann gegen pyproject. Wer den Pin dort anhob, veraenderte damit
die CI nicht; wer den in `ci.yml` anhob, veraenderte den lokalen Lauf nicht.
Zwei Angaben, die sich stumm einigen muessen, sind eine Angabe zu viel.

Der Rueckfall ist still: Er macht kein Gate rot, er laesst es lediglich mit
einer anderen Version laufen als der, gegen die lokal geprueft wurde.
"""

from __future__ import annotations

import pathlib
import re
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# Formen, in denen ein Schritt ein Paket eigenstaendig installiert. Die erste
# Fassung dieses Tests kannte nur `pip install ruff` und liess damit
# `pip install --upgrade ruff==…`, `pip install "ruff==…"`, `pip3 install`,
# `uv tool install` und `uv run --with ruff==…` durch — allesamt Formen, die
# den Pin genauso ueberstimmen. Aufgefallen ist das in einem Codex-Review.
_INSTALL_FORM = re.compile(
    r"(?:pip3?\s+install|python\s+-m\s+pip\s+install|uv\s+pip\s+install"
    r"|uv\s+tool\s+install|uv\s+add|pipx\s+install|--with)\b"
)
# ruff als eigenes Paket-Argument. Anfuehrungszeichen sind erlaubt, ein
# vorangehendes Wort-, Pfad- oder Bindestrich-Zeichen nicht: sonst zaehlten
# `ruff-lsp` und `scripts/ruff_helper.py` mit.
_RUFF_PAKET = re.compile(r"""(?<![\w./-])["']?ruff(?![\w-])""")


def _installiert_ruff(zeile: str) -> bool:
    """Installiert diese Zeile ruff als benanntes Paket?

    `pip install -e ".[dev]"` zieht ruff ebenfalls herein — das ist aber der
    richtige Weg und darf nicht anschlagen. Entscheidend ist deshalb, ob nach
    dem Install-Befehl ein eigenes Argument `ruff` steht.
    """
    treffer = _INSTALL_FORM.search(zeile)
    return bool(treffer) and bool(_RUFF_PAKET.search(zeile[treffer.end() :]))


def _workflow_dateien() -> list[pathlib.Path]:
    """Beide Endungen: GitHub laedt `*.yml` UND `*.yaml`."""
    return sorted([*_WORKFLOWS.glob("*.yml"), *_WORKFLOWS.glob("*.yaml")])


def _dev_abhaengigkeiten() -> list[str]:
    daten = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    return daten["project"]["optional-dependencies"]["dev"]


def test_ruff_ist_exakt_gepinnt() -> None:
    """Eine Spanne laesst lokalen Lauf und CI verschiedene Versionen fahren."""
    specs = [s for s in _dev_abhaengigkeiten() if re.match(r"^ruff\b", s)]
    assert len(specs) == 1, f"genau ein ruff-Specifier erwartet, gefunden: {specs}"
    assert re.fullmatch(r"ruff==\d+\.\d+\.\d+", specs[0]), (
        f"ruff muss als ruff==X.Y.Z gepinnt sein, gefunden {specs[0]!r}."
    )


def test_der_pin_ist_die_einzige_versionsquelle() -> None:
    """Kein Workflow darf ruff selbst installieren."""
    for workflow in _workflow_dateien():
        # Kommentarzeilen raus, damit ein erklaerender Hinweis auf den
        # frueheren Schritt den Test nicht selbst ausloest.
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if _installiert_ruff(z)]
        assert not treffer, (
            f"{workflow.name} installiert ruff direkt ({treffer}). Dieser Schritt "
            "laeuft nach dem dev-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_workflow_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefung oben gegen ein leeres Verzeichnis ab.

    Faende der Glob nichts, waere die Schleife leer und die Zusicherung
    trivialerweise wahr — gruen, ohne irgendetwas geprueft zu haben.
    """
    workflows = _workflow_dateien()
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )


def test_der_erkenner_kennt_die_gaengigen_installationsformen() -> None:
    """Der Scan ist nur so gut wie das, was er als Install erkennt.

    Ohne diese Tabelle ist die Zusicherung oben gruen, weil sie die Form nicht
    kennt — nicht, weil sie fehlt. Genau so war es: Die erste Fassung suchte
    woertlich nach `pip install ruff` und uebersah fuenf von sieben geprueften
    Schreibweisen.
    """
    muss_treffen = [
        "run: pip install ruff==0.16.1",
        "run: pip install --upgrade ruff==0.16.1",
        'run: pip install "ruff==0.16.1"',
        "run: pip install 'ruff==0.16.1'",
        "run: pip3 install ruff==0.16.1",
        "run: python -m pip install ruff==0.16.1",
        "run: uv pip install ruff==0.16.1 --system",
        "run: uv tool install ruff==0.16.1",
        "run: uv add ruff==0.16.1",
        "run: pipx install ruff==0.16.1",
        "run: uv run --with ruff==0.16.1 ruff check src/",
        "run: pip install ruff",
        "run: pip install pytest ruff==0.16.1",
        "run: pip install ruff[extra]==0.16.1",
    ]
    darf_nicht_treffen = [
        'run: pip install -e ".[dev]"',
        'run: uv pip install -e ".[dev]" --system',
        "run: ruff check src/ tests/ scripts/",
        "run: ruff format --check src/ tests/",
        "run: pip install ruff-lsp",
        "run: pip install uv",
        "run: python -m pip install --upgrade pip",
        "run: pip install build hatchling",
        "run: uv run --with pip-audit pip-audit",
        "run: python scripts/ruff_helper.py",
        "run: pip install -r requirements.txt",
        "name: Lint mit ruff",
    ]
    uebersehen = [z for z in muss_treffen if not _installiert_ruff(z)]
    assert not uebersehen, f"Erkenner uebersieht: {uebersehen}"
    fehlalarm = [z for z in darf_nicht_treffen if _installiert_ruff(z)]
    assert not fehlalarm, f"Erkenner schlaegt faelschlich an: {fehlalarm}"


# --- Actions: eine Major-Version je Action ---------------------------------
#
# Dieselbe Krankheit, anderer Ort. `github-script` steht in `live.yml` an zwei
# Schritten, und beide muessen dieselbe Major fahren: Laeuft der eine auf einer
# aelteren, ist nicht der Aufbau rot, sondern nur ein Schritt anders — genau die
# stille Sorte Abweichung, wegen der der ruff-Pin oben ueberhaupt existiert.
#
# `github-script@v9` ist ausserdem kein beliebiger Bump: Ab v9 ist
# `@actions/github` ESM-only, `require('@actions/github')` faellt zur Laufzeit
# um, und ein Skript, das `getOctokit` als eigene Variable deklariert, ebenso.
# Der `script:`-Koerper selbst bleibt CommonJS — `require` auf eine eigene Datei
# (`scripts/live_issue.cjs`) ist weiterhin der dokumentierte Weg. Der Test haelt
# fest, dass hier keines der beiden gebrochenen Muster einzieht.

_ACTION = re.compile(r"^\s*(?:-\s+)?uses:\s*([\w.-]+/[\w.-]+)@(\S+)", re.MULTILINE)

# Muster, die ab github-script v9 zur Laufzeit umfallen.
_ESM_BRUCH = re.compile(r"""require\(\s*["']@actions/github["']\s*\)""")
_GETOCTOKIT_DEKLARATION = re.compile(r"\b(?:const|let|var)\s+getOctokit\b")


def _aktionen() -> dict[str, set[str]]:
    """{Action-Name: {benutzte Versionen}} ueber alle Workflows."""
    gefunden: dict[str, set[str]] = {}
    for datei in _workflow_dateien():
        for name, version in _ACTION.findall(datei.read_text(encoding="utf-8")):
            gefunden.setdefault(name, set()).add(version)
    return gefunden


def test_jede_action_faehrt_ueberall_dieselbe_version() -> None:
    uneinig = {n: sorted(v) for n, v in _aktionen().items() if len(v) > 1}
    assert not uneinig, (
        f"Action-Versionen laufen auseinander: {uneinig}. Zwei Schritte mit "
        "verschiedenen Majors machen kein Gate rot — sie verhalten sich nur "
        "unterschiedlich, und zwar unbemerkt."
    )


def test_github_script_ist_mindestens_v9() -> None:
    """v7 zielt auf Node 20; der Runner zwingt es auf 24 und warnt darueber."""
    versionen = _aktionen().get("actions/github-script")
    if not versionen:  # die Action wurde entfernt — dann ist nichts zu halten
        return
    for version in versionen:
        major = re.match(r"v(\d+)", version)
        assert major, f"github-script ist nicht auf eine Major gepinnt: {version!r}"
        assert int(major.group(1)) >= 9, (
            f"github-script@{version} ist aelter als v9 — Node 20 ist abgekuendigt"
        )


def test_kein_skript_nutzt_die_in_v9_gebrochenen_muster() -> None:
    for datei in [*_workflow_dateien(), *(_ROOT / "scripts").glob("*.cjs")]:
        text = datei.read_text(encoding="utf-8")
        assert not _ESM_BRUCH.search(text), (
            f"{datei.name}: `require('@actions/github')` faellt ab v9 zur Laufzeit um"
        )
        assert not _GETOCTOKIT_DEKLARATION.search(text), (
            f"{datei.name}: `getOctokit` ist ab v9 ein Funktionsparameter und "
            "darf nicht neu deklariert werden"
        )
