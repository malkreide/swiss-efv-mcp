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

from .logging_config import configure_logging, get_logger
from .server import mcp
from .settings import get_settings

_NETWORK = {"sse", "streamable-http", "http"}


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger(__name__)

    if settings.transport in _NETWORK:
        import uvicorn
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware

        transport = "sse" if settings.transport == "sse" else "http"
        middleware = []
        if settings.cors_origins:
            middleware.append(
                Middleware(
                    CORSMiddleware,
                    allow_origins=settings.cors_origins,
                    allow_methods=["GET", "POST", "OPTIONS"],
                    allow_headers=["*"],
                    expose_headers=["Mcp-Session-Id"],
                )
            )
        app = mcp.http_app(
            transport=transport,
            allowed_origins=settings.cors_origins or None,
            middleware=middleware,
        )
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
