"""Entry point with dual transport.

TRANSPORT env var selects the mode:
  - "stdio" (default)          -> Claude Desktop
  - "sse" / "streamable-http"  -> cloud (Railway, Render); binds HOST:PORT

HOST defaults to 127.0.0.1 (loopback); set HOST=0.0.0.0 only inside a container
(the provided Dockerfile does). This keeps the SSE transport off the local
network by default.

Note: mcp.settings.host / mcp.settings.port must be set *before* mcp.run(),
not passed as kwargs. FastMCP SSE exposes /sse (not /mcp).
"""

from __future__ import annotations

import os

from .server import mcp


def main() -> None:
    transport = os.environ.get("TRANSPORT", "stdio").lower()

    if transport in {"sse", "streamable-http"}:
        mcp.settings.host = os.environ.get("HOST", "127.0.0.1")
        mcp.settings.port = int(os.environ.get("PORT", "8000"))
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
