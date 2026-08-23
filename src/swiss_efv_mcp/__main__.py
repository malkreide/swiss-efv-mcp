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

# `allow_headers` stood at `["*"]`. Starlette switches to `allow_all_headers`
# on a wildcard and mirrors back whatever a browser announces, so every listed
# origin could send any header at all — that is not an allow-list, it is the
# absence of one. It also hides every drift, because a wildcard cannot become
# wrong: drop a header the protocol needs and nothing turns red.
#
# `Last-Event-ID` is how a client resumes a dropped SSE stream
# (`LAST_EVENT_ID_HEADER` in `mcp.server.streamable_http`). Omitting it breaks
# only reconnection after packet loss — the worst way to find a bug.
#
# The `Mcp-Method` / `Mcp-Name` / `Mcp-Protocol-Version` routing headers of spec
# 2026-07-28 are deliberately **absent**: fastmcp 3.x pins `mcp` 1.x, where
# `mcp.shared.inbound` does not exist and nothing reads them. Listing headers
# this server never reads would be the same guesswork the wildcard was.
# `test_the_routing_headers_belong_here_once_the_sdk_reads_them` fails the day
# that changes.
CORS_ALLOW_HEADERS = [
    "Content-Type",
    "Mcp-Session-Id",
    "Last-Event-ID",
]


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
                allow_methods=["GET", "POST", "OPTIONS"],
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
