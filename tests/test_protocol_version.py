"""Was am Protokoll-Pin dieses Servers noch nicht gesichert war.

Ein Gate gibt es hier bereits: `test_negotiated_protocol_version_matches_pin`
in `tests/test_hardening.py` faehrt einen echten `initialize` und vergleicht
die ausgehandelte Revision mit `MCP_PROTOCOL_VERSION`. Das ist die wichtigste
Haelfte, und sie bleibt, wo sie ist.

Drei Luecken blieben daneben offen:

1. `MCP_PROTOCOL_VERSION` war eine freie Zeichenkette. Wer sie beim naechsten
   SDK-Bump nachzieht, bekommt einen gruenen Lauf — auch wenn er sich vertippt
   oder eine Revision einsetzt, die das SDK gar nicht kennt. Der Pin ist jetzt
   gegen `LATEST_PROTOCOL_VERSION` gehalten.
2. Beide READMEs nennen die Revision im Fliesstext — aber nichts hielt sie
   gegen den Pin. Zwei Prosastellen, die man beim Nachziehen uebersehen kann;
   im Portfolio sind READMEs aus genau diesem Grund schon dreimal
   auseinandergelaufen.
3. Nichts sagte, warum hier **eine** Revision steht statt eines Paares.

Zu Punkt 3: Die Schwester-Server im Portfolio pinnen ein Paar — eine
Handshake-Obergrenze und eine moderne Revision —, weil `mcp` 2.x zwei
Protokoll-Aeren ueber denselben Server bedient. Dieser Server faehrt fastmcp
3.x, und das pinnt `mcp` 1.x: dort gibt es `mcp.types.version` gar nicht.
`test_das_sdk_kennt_hier_nur_eine_aera` ist deshalb an das SDK gebunden statt
an diesen Absatz und faellt, sobald ein Upgrade die beiden Konstanten
hereinzieht.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from mcp.types import LATEST_PROTOCOL_VERSION

from swiss_efv_mcp.server import MCP_PROTOCOL_VERSION

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_der_pin_ist_die_revision_des_sdk() -> None:
    """Gegen die SDK-Konstante gehalten, nicht gegen abgeschriebenen Spec-Text.

    Der bestehende Handshake-Test faellt zwar auch, wenn das SDK die Revision
    anhebt — aber er sagt dann nur, dass zwei Werte auseinanderliegen. Diese
    Zeile benennt den Grund, und sie faellt auch bei einem Tippfehler im Pin,
    den das SDK gar nicht kennt.
    """
    assert MCP_PROTOCOL_VERSION == LATEST_PROTOCOL_VERSION, (
        f"Pin steht auf {MCP_PROTOCOL_VERSION}, das SDK auf "
        f"{LATEST_PROTOCOL_VERSION}. Beide READMEs mitziehen."
    )


@pytest.mark.parametrize("datei", ["README.md", "README.de.md"])
def test_beide_readmes_nennen_dieselbe_revision(datei: str) -> None:
    """Eine Doku, die anderes sagt als der Server tut, ist die teurere Haelfte
    des Problems: sie sieht geprueft aus.

    Beide Sprachen einzeln parametrisiert. Nur die englische zu pruefen hiesse,
    die deutsche beim naechsten Bump stehenzulassen, ohne dass es auffaellt —
    im Portfolio ist genau das schon dreimal passiert.
    """
    text = (_ROOT / datei).read_text(encoding="utf-8")
    revisionen = set(re.findall(r"`(20\d\d-\d\d-\d\d)`", text))
    assert MCP_PROTOCOL_VERSION in revisionen, (
        f"{datei} nennt {sorted(revisionen)}, erwartet {MCP_PROTOCOL_VERSION}"
    )


def test_das_sdk_kennt_hier_nur_eine_aera() -> None:
    """Warum dieser Server keinen Zwei-Aeren-Pin fuehrt — und wann er einen braucht.

    `mcp` 2.x bedient zwei Protokoll-Aeren ueber denselben Server: den alten
    `initialize`-Handshake mit eigener Obergrenze und die neuere Umschlagform
    pro Anfrage. Beide Konstanten leben in `mcp.types.version`, und
    `LATEST_PROTOCOL_VERSION` ist dort ein Alias auf die *moderne* Aera — wer
    nur gegen ihn pinnt, sichert die Aera, die heute praktisch niemand spricht.

    Unter `mcp` 1.x gibt es das Modul nicht und die Frage stellt sich nicht.
    Zieht ein fastmcp-Upgrade `mcp` 2.x herein, faellt dieser Test und sagt,
    dass der Pin auf ein Paar erweitert werden muss.
    """
    try:
        import mcp.types.version as sdk_version
    except ModuleNotFoundError:
        return  # mcp 1.x: eine Aera, nichts zu trennen

    handshake = getattr(sdk_version, "LATEST_HANDSHAKE_VERSION", None)
    modern = getattr(sdk_version, "LATEST_MODERN_VERSION", None)
    pytest.fail(
        "Das SDK fuehrt jetzt zwei Protokoll-Aeren "
        f"(Handshake {handshake}, modern {modern}). MCP_PROTOCOL_VERSION pinnt "
        "nur eine Revision und muss auf ein Paar erweitert werden, sonst sichert "
        "der Pin die Aera, die heutige Clients nicht sprechen."
    )
