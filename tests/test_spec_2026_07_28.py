"""Was an der Umstellung auf Spec `2026-07-28` sonst niemand halten wuerde.

Die Protokoll-Revision selbst haengt an `tests/test_protocol_version.py`
(Pin gegen SDK-Konstanten) und `tests/test_hardening.py` (beide Aeren mit einer
echten Verbindung nachgefahren). Hier stehen die drei Dinge, die bei der
Umstellung mit aufgefallen sind und sonst nirgends gehalten werden.
"""

from __future__ import annotations

import os
import subprocess
import sys
import warnings

import pytest
from fastmcp import Client

import swiss_efv_mcp
from swiss_efv_mcp.server import mcp


async def test_serverinfo_traegt_die_eigene_version_und_nicht_die_von_fastmcp() -> None:
    """`serverInfo.version` meldete die Version der Bibliothek, nicht die des Servers.

    Ohne `version=` im `FastMCP`-Konstruktor faellt FastMCP auf seine *eigene*
    Distributionsversion zurueck: am 18.9.2026 meldete dieser Server `4.0.5`
    statt `0.4.0`. Das faellt nicht auf, weil beides plausible Versionen sind —
    ein Client, der die Serverversion protokolliert oder gegen bekannte Fehler
    abgleicht, bekam die Nummer einer fremden Bibliothek.

    Die zweite Zusicherung ist die eigentliche: gegen `__version__` allein
    bliebe der Test auch dann gruen, wenn FastMCP seine Version je zufaellig
    auf dieselbe Nummer setzte. Sie nennt den Fehlbefund beim Namen.
    """
    import importlib.metadata as md

    async with Client(mcp) as c:
        gemeldet = c.server_info.version

    assert gemeldet == swiss_efv_mcp.__version__
    assert gemeldet != md.version("fastmcp"), (
        "serverInfo.version stimmt mit der fastmcp-Version ueberein — entweder "
        "ist `version=` wieder weggefallen, oder die Zahlen sind zufaellig gleich "
        "und dieser Test kann den Fehler gerade nicht mehr sehen."
    )


async def test_ein_werkzeugaufruf_sendet_keine_abgekuendigte_log_benachrichtigung() -> None:
    """SEP-2577 kuendigt die `logging`-Capability mit `2026-07-28` ab.

    Bis zum 18.9.2026 schickte jeder Tool-Aufruf hier ein `ctx.debug(...)` — also
    genau eine Benachrichtigung ueber die abgekuendigte Capability, auf jeder
    einzelnen Anfrage. Die Diagnose ist nicht weg, sie liegt jetzt im
    structlog-Strom auf stderr, wo die README sie ohnehin verortet.

    Geprueft wird an beidem, was ein Client sieht: der Benachrichtigung selbst
    und der Deprecation-Warnung, die das SDK dabei wirft. Nur auf die Warnung zu
    pruefen waere zu schwach — sie koennte bei einem SDK-Update verschwinden,
    waehrend die Benachrichtigung bleibt.

    FastMCP bewirbt die Capability weiterhin selbst; das ist nicht zu steuern
    und deshalb hier auch nicht zugesichert. Was dieser Server tut, ist es.
    """
    empfangen: list[object] = []

    async def log_handler(nachricht: object) -> None:
        empfangen.append(nachricht)

    async with Client(mcp, log_handler=log_handler) as c:
        assert c.protocol_version == "2026-07-28"
        with warnings.catch_warnings(record=True) as gesammelt:
            warnings.simplefilter("always")
            await c.call_tool("fiscal_status", {})

    assert empfangen == [], f"Der Aufruf schickte {len(empfangen)} Log-Benachrichtigung(en)"
    sep2577 = [w for w in gesammelt if "SEP-2577" in str(w.message)]
    assert sep2577 == [], f"Der Aufruf loeste {[str(w.message) for w in sep2577]} aus"


async def test_der_fortschritt_bleibt_erhalten() -> None:
    """Die Gegenkontrolle zum Test darueber.

    `report_progress` ist **nicht** abgekuendigt — nur die `logging`-Capability
    ist es. Ohne diese Zeile waere «keine Benachrichtigungen mehr» auch dann
    gruen, wenn beim Aufraeumen versehentlich die Fortschrittsmeldung mit
    herausgefallen waere, und der Test darueber bewiese dann das Gegenteil von
    dem, was er soll.
    """
    ereignisse: list[tuple[float, float | None]] = []

    async def progress_handler(progress: float, total: float | None, message: str | None = None):
        ereignisse.append((progress, total))

    async with Client(mcp, progress_handler=progress_handler) as c:
        await c.call_tool("fiscal_list_dimensions", {})

    assert ereignisse == [(0.0, 3.0), (3.0, 3.0)]


def test_der_eingestellte_log_level_wirkt_trotz_import_reihenfolge() -> None:
    """Die Diagnose, die aus `ctx.debug` in den structlog-Strom gewandert ist,
    muss dort auch sichtbar zu machen sein.

    `client.py` und `_otel.py` holen ihren Logger auf Modulebene. Der Aufruf
    laeuft damit schon waehrend `from .server import mcp` — also bevor `main()`
    die Settings gelesen hat — und konfigurierte auf die Vorgabe `INFO`. Solange
    `configure_logging` beim zweiten Aufruf durchlief, blieb es dabei:
    `EFV_MCP_LOG_LEVEL=DEBUG` war wirkungslos, gemessen am 18.9.2026, ohne dass
    etwas rot wurde.

    In einem eigenen Interpreter, weil der Level ein Prozess-Zustand ist: im
    laufenden Testprozess hat laengst ein anderer Test konfiguriert.

    Die zweite Haelfte ist die Gegenprobe. Ohne sie bliebe der Test auch dann
    gruen, wenn jemand die Vorgabe schlicht auf `DEBUG` setzte — dann waere der
    Level nicht *einstellbar*, sondern nur zufaellig richtig.
    """
    code = (
        "import logging, os;"
        "import swiss_efv_mcp.__main__;"  # zieht client.py und damit get_logger()
        "from swiss_efv_mcp.logging_config import configure_logging;"
        "from swiss_efv_mcp.settings import Settings;"
        "configure_logging(Settings(_env_file=None).log_level);"
        "print(logging.getLevelName(logging.getLogger().level))"
    )

    def lauf(level: str | None) -> str:
        umgebung = dict(os.environ)
        umgebung.pop("EFV_MCP_LOG_LEVEL", None)
        if level is not None:
            umgebung["EFV_MCP_LOG_LEVEL"] = level
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env=umgebung,
        ).stdout.strip()

    assert lauf("DEBUG") == "DEBUG", "EFV_MCP_LOG_LEVEL wirkt nicht"
    assert lauf(None) == "INFO", "die Vorgabe ist nicht mehr INFO — der Test oben misst dann nichts"


@pytest.mark.parametrize("modus", ["auto", "legacy"])
async def test_die_tools_antworten_in_beiden_aeren(modus: str) -> None:
    """Der Aerenwechsel darf die Tools nicht nur in *einer* Aera erreichbar lassen.

    `fiscal_status` geht nicht ans Netz und eignet sich deshalb als Sonde, die
    ohne Fixture auskommt.
    """
    async with Client(mcp, mode=modus) as c:
        namen = {t.name for t in await c.list_tools()}
        assert "fiscal_status" in namen
        ergebnis = await c.call_tool("fiscal_status", {})
    assert ergebnis.is_error is False
