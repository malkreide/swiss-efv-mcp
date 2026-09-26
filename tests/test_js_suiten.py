#!/usr/bin/env python3
"""Faehrt die JS-Suiten unter `scripts/` im bestehenden pytest-Gate.

Die Entscheidungsbaeume der geplanten Workflows sind JavaScript —
`actions/github-script` laedt sie. Ihre Tests liegen deshalb neben ihnen als
`*.test.mjs` und laufen unter `node:test`. Damit sie niemand vergisst, ruft
dieser Wrapper sie mit: keine zweite Zeile in `ci.yml`, kein sechstes Gate,
das man kennen muss.

WARUM PER GLOB UND NICHT PER LISTE

Diese Datei hiess bis zum 26.9.2026 `test_live_issue.py` und kannte genau eine
Suite. Als `nightly_issue.test.mjs` dazukam, waren zwei Wege offen: die Datei
kopieren oder sie oeffnen. Kopieren haette den Harness verdoppelt — samt der
Zaehlung unten, die eine echte Falle abdeckt, und damit samt der Moeglichkeit,
dass die beiden Kopien auseinanderlaufen. Dieselbe Konstruktion, an der hier
schon der ruff-Pin gescheitert ist.

Der Glob hat zusaetzlich die Eigenschaft, die eine Liste nicht hat: Die
naechste Suite laeuft mit, ohne dass jemand daran denkt.

WARUM DIE TESTS GEZAEHLT WERDEN

Der Exit-Code allein reicht nicht, und `# tests > 0` reicht auch nicht: Eine
Datei ohne einen einzigen `test(...)`-Aufruf meldet unter `node --test` genau
`# tests 1  # pass 1` — die Datei selbst gilt als bestandener Test. Gemessen an
Node 22.22, und zwar erst in der Gegenprobe: Die Suite wurde durch einen
Kommentar ersetzt, und dieser Wrapper blieb gruen.

Das ist dieselbe Falle wie die uebersprungene Live-Suite, nur eine Ebene
tiefer — ein Erfolg, der nichts geprueft hat. Deshalb wird die Zahl der
bestandenen Tests gegen die Zahl der in der Suite deklarierten gehalten. Sie
muessen uebereinstimmen, und es muss mindestens einen geben.

Was das NICHT faengt: einen geloeschten Test. Dann sinken beide Zahlen, und sie
stimmen weiter ueberein. Das ist Absicht — eine Loeschung steht im Diff, und
eine fest verdrahtete Untergrenze waere genau die Zahl, die beim naechsten neuen
Test wieder nicht stimmt.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"

# In der CI ist Node auf `ubuntu-latest` immer da. Faellt der Test dort auf
# «uebersprungen» zurueck, waere das genau der stille Erfolg, den dieses Repo
# schon einmal geprueft und verworfen hat.
_IN_CI = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


def _suiten() -> list[Path]:
    return sorted(_SCRIPTS.glob("*.test.mjs"))


def _node() -> str | None:
    return shutil.which("node")


def _bilanz(ausgabe: str) -> dict[str, int]:
    """Die `# tests`/`# pass`/`# fail`-Zeilen aus der TAP-Ausgabe."""
    gefunden = {}
    for feld in ("tests", "pass", "fail", "skipped", "todo"):
        treffer = re.search(rf"^# {feld} (\d+)$", ausgabe, re.MULTILINE)
        if treffer:
            gefunden[feld] = int(treffer.group(1))
    return gefunden


def _deklarierte_tests(suite: Path) -> int:
    """`test('…')`-Aufrufe am Zeilenanfang der Suite.

    Die Gegenzahl zur TAP-Bilanz: Nur wenn beide gleich sind, ist jeder
    geschriebene Fall auch gelaufen.
    """
    return len(re.findall(r"^test\(", suite.read_text(encoding="utf-8"), re.MULTILINE))


def test_es_gibt_ueberhaupt_suiten() -> None:
    """Der Glob koennte leer laufen — dann pruefte diese Datei nichts mehr,
    und die Parametrisierung darunter erzeugte schlicht keinen Test."""
    assert _suiten(), f"keine *.test.mjs unter {_SCRIPTS}"


def test_node_ist_in_der_ci_vorhanden() -> None:
    """Sonst wuerde der eigentliche Test still uebersprungen."""
    if not _IN_CI:
        pytest.skip("nur in der CI: lokal darf Node fehlen")
    assert _node(), "Node fehlt in der CI — die JS-Tests liefen nicht"


@pytest.mark.parametrize("suite", _suiten(), ids=lambda p: p.name)
def test_der_entscheidungsbaum_haelt(suite: Path) -> None:
    node = _node()
    if not node:
        pytest.skip("node nicht im PATH — `test_node_ist_in_der_ci_vorhanden` deckt die CI ab")
    assert suite.is_file(), f"{suite} fehlt"

    lauf = subprocess.run(  # noqa: S603 — fester Befehl, kein fremder Text
        # Ein Ordner-Argument (`node --test scripts/`) laesst Node den Ordner
        # als Modul aufloesen und mit MODULE_NOT_FOUND scheitern, gemessen an
        # Node 22.22. Die Datei wird deshalb einzeln benannt.
        [node, "--test", str(suite)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    ausgabe = lauf.stdout + lauf.stderr
    bilanz = _bilanz(ausgabe)

    # Erst die Bilanz, dann der Exit-Code: Sie sagt, WAS schiefging.
    assert bilanz, f"keine TAP-Bilanz in der Ausgabe:\n{ausgabe[-2000:]}"
    assert bilanz.get("fail", 0) == 0, f"JS-Tests rot:\n{ausgabe[-4000:]}"
    assert bilanz.get("skipped", 0) == 0, f"JS-Tests uebersprungen:\n{ausgabe[-2000:]}"

    deklariert = _deklarierte_tests(suite)
    assert deklariert > 0, f"{suite.name} deklariert keinen Test mehr"
    assert bilanz.get("pass") == deklariert, (
        f"{deklariert} Test(s) in {suite.name} deklariert, aber {bilanz.get('pass')} "
        f"bestanden — eine Datei ohne Tests meldet `# pass 1`, ohne etwas zu pruefen:"
        f"\n{ausgabe[-2000:]}"
    )
    assert lauf.returncode == 0, f"node endete mit {lauf.returncode}:\n{ausgabe[-2000:]}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
