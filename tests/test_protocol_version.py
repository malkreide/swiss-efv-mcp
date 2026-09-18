"""Der Protokoll-Pin dieses Servers — jetzt ein Paar statt einer Zeichenkette.

Bis zum 18.9.2026 stand hier **eine** Revision, `2025-11-25`, mit der
Begruendung: fastmcp 3.x pinne `mcp` 1.x, und dort gebe es nur eine
Protokoll-Aera. Diese Datei trug den Test, der genau diese Begruendung an das
SDK band statt an einen Kommentar — `test_das_sdk_kennt_hier_nur_eine_aera`.
Er hat ausgeloest: `fastmcp>=3.4` loeste am 18.9.2026 zu fastmcp 4.0.5 auf,
das `mcp` 2.2.0 mitbringt, und damit gibt es zwei Aeren:

  - **Handshake** (`initialize`), Obergrenze `LATEST_HANDSHAKE_VERSION`
  - **modern** (`server/discover` + Umschlag pro Anfrage),
    `LATEST_MODERN_VERSION` — das ist `2026-07-28`

Warum ein Paar und nicht einfach der neuere Wert: `LATEST_PROTOCOL_VERSION` ist
in `mcp` 2.x ein Alias auf die *moderne* Aera. Wer nur dagegen pinnt, sagt
nichts darueber, was ein Client der alten Aera bekommt — und der Handshake wird
weiterhin bedient. Ein Pin, der nur eine der beiden Aeren beschreibt, sieht
geprueft aus und ist es zur Haelfte.

Die Zusicherungen hier sind bewusst gegen die SDK-Konstanten gehalten und nicht
gegen abgeschriebenen Spec-Text: ein Tippfehler im Pin faellt damit auch dann
auf, wenn er zufaellig wie eine Revision aussieht.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from swiss_efv_mcp.server import (
    MCP_HANDSHAKE_PROTOCOL_VERSION,
    MCP_MODERN_PROTOCOL_VERSION,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_das_sdk_fuehrt_weiterhin_zwei_aeren() -> None:
    """Die Voraussetzung des Paares, an das SDK gebunden.

    Faellt `mcp` je wieder auf eine Aera zurueck — oder kommt eine dritte —,
    sagt dieser Test es, bevor die beiden Tests darunter raten muessen, welche
    Konstante sie meinen. Unter `mcp` 1.x gibt es `mcp.types.version` gar nicht;
    der Import faellt dann, und das ist die richtige Meldung: `fastmcp>=4.0` in
    `pyproject.toml` ist unterschritten.
    """
    from mcp.types import version as sdk_version

    assert hasattr(sdk_version, "LATEST_HANDSHAKE_VERSION")
    assert hasattr(sdk_version, "LATEST_MODERN_VERSION")
    assert sdk_version.MODERN_PROTOCOL_VERSIONS == (sdk_version.LATEST_MODERN_VERSION,), (
        "Das SDK serviert jetzt mehr als eine moderne Revision "
        f"({sdk_version.MODERN_PROTOCOL_VERSIONS}). Der Pin nennt genau eine und "
        "muss erweitert werden."
    )


def test_der_moderne_pin_ist_die_moderne_revision_des_sdk() -> None:
    from mcp.types.version import LATEST_MODERN_VERSION

    assert MCP_MODERN_PROTOCOL_VERSION == LATEST_MODERN_VERSION, (
        f"Pin steht auf {MCP_MODERN_PROTOCOL_VERSION}, das SDK auf "
        f"{LATEST_MODERN_VERSION}. Beide READMEs mitziehen."
    )


def test_der_handshake_pin_ist_die_handshake_obergrenze_des_sdk() -> None:
    from mcp.types.version import LATEST_HANDSHAKE_VERSION

    assert MCP_HANDSHAKE_PROTOCOL_VERSION == LATEST_HANDSHAKE_VERSION, (
        f"Pin steht auf {MCP_HANDSHAKE_PROTOCOL_VERSION}, das SDK auf {LATEST_HANDSHAKE_VERSION}."
    )


def test_die_beiden_aeren_sind_verschieden() -> None:
    """Sonst waere das Paar eine verdoppelte Zeichenkette und keine Aussage.

    Ohne diese Zeile blieben die beiden Tests darueber auch dann gruen, wenn
    jemand beide Pins auf denselben Wert setzt — und genau dann waere die
    Unterscheidung, um derentwillen das Paar existiert, wieder weg.
    """
    assert MCP_MODERN_PROTOCOL_VERSION != MCP_HANDSHAKE_PROTOCOL_VERSION


@pytest.mark.parametrize("datei", ["README.md", "README.de.md"])
@pytest.mark.parametrize(
    "revision",
    [MCP_MODERN_PROTOCOL_VERSION, MCP_HANDSHAKE_PROTOCOL_VERSION],
)
def test_beide_readmes_nennen_beide_revisionen(datei: str, revision: str) -> None:
    """Eine Doku, die anderes sagt als der Server tut, ist die teurere Haelfte
    des Problems: sie sieht geprueft aus.

    Zweifach parametrisiert. Nur die englische zu pruefen hiesse, die deutsche
    beim naechsten Bump stehenzulassen, ohne dass es auffaellt — im Portfolio
    ist genau das schon dreimal passiert. Und nur die moderne Revision zu
    pruefen hiesse, die Aera unerwaehnt zu lassen, die aeltere Clients
    tatsaechlich bekommen.
    """
    text = (_ROOT / datei).read_text(encoding="utf-8")
    revisionen = set(re.findall(r"`(20\d\d-\d\d-\d\d)`", text))
    assert revision in revisionen, f"{datei} nennt {sorted(revisionen)}, erwartet {revision}"
