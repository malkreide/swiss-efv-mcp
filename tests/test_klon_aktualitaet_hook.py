"""Der SessionStart-Hook meldet einen veralteten Klon -- und blockiert nie.

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache nicht im Diff stand: Es fehlten jeweils genau die Commits, die das
Gate einfuehrten, an dem der Branch scheiterte.

Geprueft wird gegen echte Wegwerf-Repositories, nicht gegen eine Nachbildung
von git. Eine handgeschriebene Nachbildung kodierte nur die Annahme des
Autors darueber, was git tut, und koennte sie nicht widerlegen -- gerade der
Default-Branch-Fall lebt davon, dass `git clone` `origin/HEAD` wirklich so
setzt, wie hier unterstellt wird.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import subprocess
import time

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude" / "hooks" / "klon-aktualitaet.sh"
_SETTINGS = _ROOT / ".claude" / "settings.json"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git fehlt")


def _git_umgebung() -> dict[str, str]:
    """git ohne Nutzer- und Systemkonfiguration und ohne interaktive Abfrage.

    Ohne das entscheidet die Konfiguration des ausfuehrenden Rechners mit --
    etwa ein `init.defaultBranch`, das den Default-Branch-Test lautlos
    umschreibt.
    """
    umgebung = dict(os.environ)
    umgebung.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return umgebung


def _git(*argumente: str, cwd: pathlib.Path) -> None:
    subprocess.run(
        ["git", *argumente],
        cwd=cwd,
        env=_git_umgebung(),
        check=True,
        capture_output=True,
    )


def _commit(repo: pathlib.Path, text: str) -> None:
    (repo / "datei.txt").write_text(text, encoding="utf-8")
    _git("add", "datei.txt", cwd=repo)
    _git("commit", "-m", text, cwd=repo)


def _upstream(basis: pathlib.Path, branch: str) -> pathlib.Path:
    """Ein Repository mit genau diesem Default-Branch."""
    repo = basis / "upstream"
    repo.mkdir()
    _git("init", cwd=repo)
    # Statt `git init -b`: funktioniert auch mit git < 2.28 und ist von
    # `init.defaultBranch` unabhaengig.
    _git("symbolic-ref", "HEAD", f"refs/heads/{branch}", cwd=repo)
    _commit(repo, "start")
    return repo


def _klon(basis: pathlib.Path, upstream: pathlib.Path) -> pathlib.Path:
    ziel = basis / "klon"
    _git("clone", str(upstream), str(ziel), cwd=basis)
    return ziel


def _hook(
    klon: pathlib.Path,
    *,
    quelle: str = "startup",
    pfad_praefix: pathlib.Path | None = None,
    timeout_sekunden: str | None = None,
) -> subprocess.CompletedProcess[str]:
    umgebung = _git_umgebung()
    umgebung["CLAUDE_PROJECT_DIR"] = str(klon)
    if pfad_praefix is not None:
        umgebung["PATH"] = f"{pfad_praefix}{os.pathsep}{umgebung['PATH']}"
    if timeout_sekunden is not None:
        umgebung["KLON_CHECK_TIMEOUT"] = timeout_sekunden
    eingabe = json.dumps({"hook_event_name": "SessionStart", "source": quelle})
    return subprocess.run(
        [str(_HOOK)],
        input=eingabe,
        env=umgebung,
        capture_output=True,
        text=True,
        timeout=60,
    )


# --- Registrierung ----------------------------------------------------------


def test_hook_ist_ausfuehrbar() -> None:
    """Ohne x-Bit startet der Hook nicht -- und meldet damit nie etwas."""
    assert _HOOK.is_file()
    assert _HOOK.stat().st_mode & stat.S_IXUSR


def test_hook_ist_in_settings_registriert() -> None:
    """Ein Skript, das niemand aufruft, prueft nichts."""
    einstellungen = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    befehle = [
        eintrag["command"]
        for gruppe in einstellungen["hooks"]["SessionStart"]
        for eintrag in gruppe["hooks"]
    ]
    assert any(_HOOK.name in befehl for befehl in befehle), befehle


# --- Kernverhalten ----------------------------------------------------------


def test_veralteter_klon_meldet_anzahl_und_branch(tmp_path: pathlib.Path) -> None:
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)
    _commit(upstream, "zwei")
    _commit(upstream, "drei")

    ergebnis = _hook(klon)

    assert ergebnis.returncode == 0
    assert "2" in ergebnis.stdout
    assert "origin/main" in ergebnis.stdout


def test_aktueller_klon_schweigt(tmp_path: pathlib.Path) -> None:
    """Bei 0 fehlenden Commits keine Ausgabe.

    Ein Hook, der bei jedem Start etwas sagt, wird zur Tapete: Die eine
    Meldung, auf die es ankommt, geht dann in den taeglichen unter.
    """
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)

    ergebnis = _hook(klon)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""


def test_eigene_commits_voraus_zaehlen_nicht(tmp_path: pathlib.Path) -> None:
    """Gezaehlt wird HEAD..origin, nicht der symmetrische Abstand.

    Ein Branch mit eigener Arbeit ist nicht veraltet, solange ihm nichts
    fehlt -- ein `--count --left-right` haette hier faelschlich gemeldet.
    """
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)
    _commit(klon, "eigene arbeit")

    ergebnis = _hook(klon)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""


def test_default_branch_master_wird_ermittelt(tmp_path: pathlib.Path) -> None:
    """`master` statt `main` -- die Annahme, die einen Branch 15 Commits alt liess.

    Die Gegenprobe steht mit im Test: Ein fest verdrahtetes `origin/main`
    scheitert in diesem Repository, und zwar mit einer Meldung, die wie ein
    Netzproblem aussieht.
    """
    upstream = _upstream(tmp_path, "master")
    klon = _klon(tmp_path, upstream)
    _commit(upstream, "zwei")

    fest_verdrahtet = subprocess.run(
        ["git", "fetch", "origin", "main"],
        cwd=klon,
        env=_git_umgebung(),
        capture_output=True,
        text=True,
    )
    assert fest_verdrahtet.returncode != 0
    assert "couldn't find remote ref main" in fest_verdrahtet.stderr

    ergebnis = _hook(klon)

    assert ergebnis.returncode == 0
    assert "origin/master" in ergebnis.stdout
    assert "1" in ergebnis.stdout


def test_detached_head_meldet_statt_abzubrechen(tmp_path: pathlib.Path) -> None:
    """Ohne Branch-Namen bleibt der Abstand zaehlbar."""
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)
    _commit(upstream, "zwei")
    _git("checkout", "--detach", "HEAD", cwd=klon)

    ergebnis = _hook(klon)

    assert ergebnis.returncode == 0
    assert "detached HEAD" in ergebnis.stdout
    assert "origin/main" in ergebnis.stdout


# --- Niemals blockieren -----------------------------------------------------


def test_kaputtes_remote_geht_still_durch(tmp_path: pathlib.Path) -> None:
    """Zeigt `origin` ins Leere, schweigt der Hook -- er meldet keinen Fehler."""
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)
    _git("remote", "set-url", "origin", str(tmp_path / "weg-damit"), cwd=klon)
    shutil.rmtree(upstream)

    ergebnis = _hook(klon)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""


def test_ohne_remote_geht_still_durch(tmp_path: pathlib.Path) -> None:
    repo = tmp_path / "solo"
    repo.mkdir()
    _git("init", cwd=repo)
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=repo)
    _commit(repo, "start")

    ergebnis = _hook(repo)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""


def test_kein_repository_geht_still_durch(tmp_path: pathlib.Path) -> None:
    kein_repo = tmp_path / "leer"
    kein_repo.mkdir()

    ergebnis = _hook(kein_repo)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""


def test_repository_ohne_commit_geht_still_durch(tmp_path: pathlib.Path) -> None:
    """Frisch initialisiert: HEAD zeigt auf nichts, `rev-list` waere ein Fehler."""
    repo = tmp_path / "frisch"
    repo.mkdir()
    _git("init", cwd=repo)

    ergebnis = _hook(repo)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""


def test_haengendes_netz_laeuft_in_die_zeitgrenze(tmp_path: pathlib.Path) -> None:
    """Ein Remote, das nicht antwortet, haelt den Sessionstart nicht an.

    Statt eine echte, flatternde Verbindung zu erhoffen, wird `git` fuer
    `ls-remote` und `fetch` durch einen Platzhalter ersetzt, der schlaeft.
    Das ist der Fall, der den Hook sonst abschalten liesse: Wer zweimal 40
    Sekunden auf den Sessionstart wartet, entfernt ihn.
    """
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)
    _commit(upstream, "zwei")

    echtes_git = shutil.which("git")
    assert echtes_git is not None
    bin_verzeichnis = tmp_path / "bin"
    bin_verzeichnis.mkdir()
    platzhalter = bin_verzeichnis / "git"
    platzhalter.write_text(
        "#!/usr/bin/env bash\n"
        'for argument in "$@"; do\n'
        '  case "$argument" in\n'
        "    ls-remote | fetch) sleep 60; exit 0 ;;\n"
        "  esac\n"
        "done\n"
        f'exec {echtes_git} "$@"\n',
        encoding="utf-8",
    )
    platzhalter.chmod(0o755)

    beginn = time.monotonic()
    ergebnis = _hook(klon, pfad_praefix=bin_verzeichnis, timeout_sekunden="2")
    gedauert = time.monotonic() - beginn

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""
    # Zwei Aufrufe unter je 2 s Grenze, plus Anlauf. Ohne Zeitgrenze waeren
    # es 60 s.
    assert gedauert < 20, gedauert


def test_compact_prueft_nicht_erneut(tmp_path: pathlib.Path) -> None:
    """SessionStart feuert auch mitten in der Sitzung; dann ist nichts zu tun."""
    upstream = _upstream(tmp_path, "main")
    klon = _klon(tmp_path, upstream)
    _commit(upstream, "zwei")

    ergebnis = _hook(klon, quelle="compact")

    assert ergebnis.returncode == 0
    assert ergebnis.stdout.strip() == ""
