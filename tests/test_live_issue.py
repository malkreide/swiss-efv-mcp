#!/usr/bin/env python3
"""Faehrt die JS-Tests von `scripts/live_issue.cjs` im bestehenden pytest-Gate.

Der Entscheidungsbaum des Live-Workflows ist JavaScript — `actions/github-script`
laedt ihn. Seine Tests liegen deshalb in `scripts/live_issue.test.mjs` und
laufen unter `node:test`. Damit sie niemand vergisst, ruft dieser Wrapper sie
mit: keine zweite Zeile in `ci.yml`, kein sechstes Gate, das man kennen muss.

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
_SUITE = _ROOT / "scripts" / "live_issue.test.mjs"

# Ein Ordner-Argument (`node --test scripts/`) laesst Node den Ordner als Modul
# aufloesen und mit MODULE_NOT_FOUND scheitern, gemessen an Node 22.22. Die
# Datei wird deshalb einzeln benannt.
_BEFEHL = ["--test", str(_SUITE)]

# In der CI ist Node auf `ubuntu-latest` immer da. Faellt der Test dort auf
# «uebersprungen» zurueck, waere das genau der stille Erfolg, den dieses Repo
# schon einmal geprueft und verworfen hat.
_IN_CI = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


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


def _deklarierte_tests() -> int:
    """`test('…')`-Aufrufe am Zeilenanfang der Suite.

    Die Gegenzahl zur TAP-Bilanz: Nur wenn beide gleich sind, ist jeder
    geschriebene Fall auch gelaufen.
    """
    return len(re.findall(r"^test\(", _SUITE.read_text(encoding="utf-8"), re.MULTILINE))


def test_node_ist_in_der_ci_vorhanden():
    """Sonst wuerde der eigentliche Test still uebersprungen."""
    if not _IN_CI:
        pytest.skip("nur in der CI: lokal darf Node fehlen")
    assert _node(), "Node fehlt in der CI — die JS-Tests liefen nicht"


def test_der_entscheidungsbaum_haelt():
    node = _node()
    if not node:
        pytest.skip("node nicht im PATH — `test_node_ist_in_der_ci_vorhanden` deckt die CI ab")
    assert _SUITE.is_file(), f"{_SUITE} fehlt"

    lauf = subprocess.run(  # noqa: S603 — fester Befehl, kein fremder Text
        [node, *_BEFEHL],
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

    deklariert = _deklarierte_tests()
    assert deklariert > 0, f"{_SUITE.name} deklariert keinen Test mehr"
    assert bilanz.get("pass") == deklariert, (
        f"{deklariert} Test(s) in {_SUITE.name} deklariert, aber {bilanz.get('pass')} "
        f"bestanden — eine Datei ohne Tests meldet `# pass 1`, ohne etwas zu pruefen:"
        f"\n{ausgabe[-2000:]}"
    )
    assert lauf.returncode == 0, f"node endete mit {lauf.returncode}:\n{ausgabe[-2000:]}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
