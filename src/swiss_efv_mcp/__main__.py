"""Entry point with dual transport.

The ``TRANSPORT`` env var (or ``EFV_MCP_TRANSPORT``) selects the mode:
  - "stdio" (default)                    -> Claude Desktop
  - "sse" / "streamable-http" / "http"   -> cloud (Railway, Render); binds HOST:PORT

HOST defaults to 127.0.0.1 (loopback); set HOST=0.0.0.0 only inside a container
(the provided Dockerfile does). This keeps the network transport off the local
network by default (SEC-016).

For network transports the ASGI app is built via ``mcp.http_app(...)`` with
default-deny CORS (browser origins must be listed explicitly via
``EFV_MCP_CORS_ORIGINS``) and served with uvicorn (SDK-004).
"""

from __future__ import annotations

from ._otel import setup_otel
from .logging_config import configure_logging, get_logger
from .server import mcp
from .settings import get_settings

_NETWORK = {"sse", "streamable-http", "http"}

# Die drei Routing-Header der Spec `2026-07-28` standen hier bis zum 18.9.2026
# **nicht**, mit der Begruendung, fastmcp 3.x pinne `mcp` 1.x und lese sie gar
# nicht. Die Begruendung ist weggefallen: `fastmcp>=4` zieht `mcp` 2.x herein,
# und `mcp.server._streamable_http_modern` liest sie auf jeder Anfrage der
# modernen Aera. `classify_inbound_request` weist eine Anfrage, deren
# `Mcp-Protocol-Version` / `Mcp-Method` / `Mcp-Name` nicht zum Umschlag passen,
# mit `HEADER_MISMATCH` (-32020) ab — ein Browser-Client, dem der Preflight
# diese Header verbietet, kommt gar nicht erst bis dorthin.
#
# Gemessen, nicht abgeschrieben: die Namen kommen aus `mcp.shared.inbound`, und
# `test_die_routing_header_stehen_in_der_freigabeliste` haelt die Liste gegen
# genau diese Konstanten.
#
# `Mcp-Param-*` (Praefix `MCP_PARAM_HEADER_PREFIX`) steht bewusst nicht hier.
# Erstens kann eine CORS-Freigabeliste kein Praefix ausdruecken — sie nennt
# Namen. Zweitens sendet ein Client solche Header nur fuer Parameter, deren
# Schema die Annotation `x-mcp-header` traegt; kein Tool dieses Servers tut das.
# Sie zu raten waere dieselbe Wildcard in klein.
# `test_kein_tool_verlangt_einen_mcp_param_header` faellt an dem Tag, an dem ein
# Tool die Annotation bekommt.
#
# `Last-Event-ID` ist, wie ein Client einen abgerissenen SSE-Strom fortsetzt
# (`LAST_EVENT_ID_HEADER` in `mcp.server.streamable_http`). Fehlt er, bricht
# ausschliesslich die Wiederaufnahme nach Paketverlust — die schlechteste Art,
# einen Fehler zu finden.
#
# `Mcp-Session-Id` gehoert der Handshake-Aera: die moderne ist sessionlos. Er
# bleibt, weil `mode="legacy"` weiterhin bedient wird.
#
# `allow_headers` stand einmal auf `["*"]`. Starlette schaltet auf einer
# Wildcard nach `allow_all_headers` und spiegelt zurueck, was ein Browser
# ankuendigt — das ist keine Freigabeliste, sondern ihr Fehlen. Es verbirgt
# ausserdem jede Drift, weil eine Wildcard nicht falsch werden kann: faellt ein
# Header weg, den das Protokoll braucht, bleibt trotzdem alles gruen.
CORS_ALLOW_HEADERS = [
    "Content-Type",
    "Mcp-Session-Id",
    "Last-Event-ID",
    "Mcp-Protocol-Version",
    "Mcp-Method",
    "Mcp-Name",
]

# `DELETE` beendet eine Session ausdruecklich. Es fehlte hier, und der Preflight
# wies die Methode mit 400 ab — ein Browser-Client konnte also Sessions oeffnen,
# aber nie schliessen. Das SDK bedient sie sehr wohl: `_handle_delete_request`
# in `mcp.server.streamable_http`, und dessen eigene 405-Antwort wirbt mit
# `Allow: GET, POST, DELETE`. Die Freigabeliste war schmaler als der Server.
#
# `OPTIONS` steht mit auf der Liste, obwohl Starlette den Preflight selbst
# beantwortet — so nennt die Liste vollstaendig, was am Endpunkt zulaessig ist,
# statt eine Methode auszulassen, die jeder Browser als Erstes schickt.
CORS_ALLOW_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]


def build_http_app(settings=None):
    """Build the network-transport ASGI app with CORS, without binding a socket.

    Pulled out of `main` so the CORS layer can be exercised: while it sat inline
    next to `uvicorn.run`, the allow-list could only be read, never tried — and
    a list that reads correctly can still never reach the middleware.
    """
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware

    settings = settings if settings is not None else get_settings()
    transport = "sse" if settings.transport == "sse" else "http"
    middleware = []
    if settings.cors_origins:
        middleware.append(
            Middleware(
                CORSMiddleware,
                allow_origins=settings.cors_origins,
                allow_methods=CORS_ALLOW_METHODS,
                allow_headers=CORS_ALLOW_HEADERS,
                expose_headers=["Mcp-Session-Id"],
            )
        )
    return mcp.http_app(
        transport=transport,
        allowed_origins=settings.cors_origins or None,
        middleware=middleware,
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_otel(settings.otel_enabled)  # OBS-006: no-op unless enabled + extra installed
    log = get_logger(__name__)

    if settings.transport in _NETWORK:
        import uvicorn

        transport = "sse" if settings.transport == "sse" else "http"
        app = build_http_app(settings)
        log.info(
            "starting_network_transport",
            transport=transport,
            host=settings.host,
            port=settings.port,
            cors_origins=settings.cors_origins,
        )
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )
    else:
        log.info("starting_stdio_transport")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
