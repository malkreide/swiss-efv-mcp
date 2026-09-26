#!/usr/bin/env python3
"""Der naechtliche Lauf faehrt DIESELBEN Gates wie der PR — nicht eine Kopie.

WOFUER DER WORKFLOW DA IST

`ci.yml` laeuft bei Push und Pull Request. Eine Codebasis, die niemand
anfasst, wird damit nie wieder geprueft — und kann trotzdem kaputtgehen: jede
Abhaengigkeit mit offener Untergrenze loest bei der naechsten frischen
Installation etwas anderes auf. Am 18.9.2026 loeste `fastmcp>=3.4` zu fastmcp 4
auf und vier Gates fielen; der letzte gruene Lauf auf `main` stammte vom 30.8.
Drei Wochen latent rot, ohne dass ein Commit die Ursache trug.

WAS HIER GEHALTEN WIRD

Nicht, dass es den Workflow gibt — das saehe man. Sondern dass er die fuenf
Gates nicht ein zweites Mal aufschreibt. Zwei Listen, die sich stumm einigen
muessen, sind eine zu viel: genau daran ist hier schon der ruff-Pin
gescheitert (`test_werkzeug_versionen.py`). Ein naechtliches Gate, das eine
andere Version faehrt als das im PR, ist schlimmer als keines — es sieht nach
Deckung aus.

Die Gate-Befehle werden deshalb AUS `ci.yml` GELESEN und nicht hier noch
einmal hingeschrieben. Sonst truege dieser Test selbst die dritte Kopie.

WARUM TEXT UND KEIN YAML-PARSER

`pyyaml` ist in dieser Umgebung nur transitiv vorhanden und in `pyproject.toml`
nicht deklariert; ein Test darauf zu bauen hiesse, ihn an eine Abhaengigkeit zu
haengen, die niemand gewollt hat und die ohne Diff verschwinden kann. Die
Zusage ist ohnehin textueller Natur: Wer die Gates kopiert, dessen Befehle
stehen danach woertlich in der Datei.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"
_CI = _WORKFLOWS / "ci.yml"
_NIGHTLY = _WORKFLOWS / "nightly.yml"
_LIVE = _WORKFLOWS / "live.yml"

# Ein Befehl, der ein Gate faehrt: die Skripte und die beiden ruff-Aufrufe.
# Absichtlich an dem festgemacht, was ein Gate AUSMACHT, nicht an der
# Formatierung der Zeile.
_GATE_BEFEHL = re.compile(r"(pytest\s+tests/|ruff\s+(?:check|format)|scripts/check_\w+\.py)")


def _gate_befehle_aus_ci() -> set[str]:
    """Die Gate-Zeilen, wie sie in `ci.yml` stehen."""
    return {
        zeile.strip()
        for zeile in _CI.read_text(encoding="utf-8").splitlines()
        if _GATE_BEFEHL.search(zeile) and not zeile.strip().startswith("#")
    }


def _crons(datei: pathlib.Path) -> list[str]:
    return re.findall(
        r"^\s*-\s*cron:\s*[\"']([^\"']+)[\"']", datei.read_text(encoding="utf-8"), re.M
    )


def test_es_gibt_den_naechtlichen_workflow() -> None:
    assert _NIGHTLY.is_file(), f"{_NIGHTLY} fehlt"


def test_er_laeuft_nach_plan() -> None:
    """Ohne `schedule` ist er nur ein Knopf, den nachts niemand drueckt."""
    assert _crons(_NIGHTLY), "nightly.yml hat keinen cron"


def test_ci_laesst_sich_ueberhaupt_aufrufen() -> None:
    """Ohne `workflow_call` in `ci.yml` scheitert der Aufruf beim ersten Lauf."""
    assert re.search(r"^\s*workflow_call:", _CI.read_text(encoding="utf-8"), re.M), (
        "ci.yml hat keinen workflow_call-Ausloeser — nightly.yml kann es nicht aufrufen"
    )


def test_der_naechtliche_lauf_ruft_ci_auf() -> None:
    assert re.search(
        r"uses:\s*\./\.github/workflows/ci\.yml", _NIGHTLY.read_text(encoding="utf-8")
    ), "nightly.yml ruft ci.yml nicht auf"


def test_die_gates_stehen_nicht_ein_zweites_mal_da() -> None:
    """Die eigentliche Zusicherung.

    Faellt an dem Tag, an dem jemand die fuenf Schritte aus `ci.yml` in
    `nightly.yml` hineinkopiert — auch dann, wenn beide Kopien in diesem Moment
    dasselbe sagen. Genau so sah der ruff-Pin aus, bevor er auseinanderlief.
    """
    aus_ci = _gate_befehle_aus_ci()
    assert aus_ci, "in ci.yml keine Gate-Befehle gefunden — der Test misst dann nichts"

    nightly = _NIGHTLY.read_text(encoding="utf-8")
    doppelt = sorted(b for b in aus_ci if b in nightly)
    assert not doppelt, (
        f"nightly.yml enthaelt Gate-Befehle woertlich aus ci.yml statt sie aufzurufen: {doppelt}"
    )


def test_er_kollidiert_nicht_mit_der_live_suite() -> None:
    """Beide nachts, aber nicht zur selben Minute.

    Laufen sie gleichzeitig, sagt ein roter Morgen nicht mehr, ob die Gates
    oder die Quelle das Problem sind — und genau diese Unterscheidung ist der
    Grund, warum es zwei Workflows sind.
    """
    gemeinsam = set(_crons(_NIGHTLY)) & set(_crons(_LIVE))
    assert not gemeinsam, f"nightly.yml und live.yml teilen sich einen cron: {gemeinsam}"


@pytest.mark.parametrize("datei", [_NIGHTLY, _LIVE])
def test_der_hinweis_auf_den_default_branch_steht_drin(datei: pathlib.Path) -> None:
    """`schedule` greift nur auf dem Default-Branch.

    Wer das nicht weiss, aendert den cron in einem PR und wartet eine Nacht
    auf einen Lauf, der nicht kommen kann. `live.yml` traegt den Hinweis seit
    seiner Einfuehrung; er gehoert in jeden geplanten Workflow.
    """
    assert "Default-Branch" in datei.read_text(encoding="utf-8"), (
        f"{datei.name} warnt nicht, dass `schedule` nur auf dem Default-Branch greift"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
