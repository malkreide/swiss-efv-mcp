"""Structured logging (OBS-003 remediation).

structlog emits JSON to **stderr** so it never contaminates the stdio JSON-RPC
stream on stdout (OBS-004). Configuration is idempotent — calling
:func:`configure_logging` more than once is safe.
"""

from __future__ import annotations

import logging
import sys

import structlog

_configured_level: str | None = None
"""Der zuletzt konfigurierte Level, oder `None`, solange nichts konfiguriert ist."""


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to write JSON logs to stderr.

    Idempotent *pro Level*: derselbe Level zweimal ist ein No-op, ein anderer
    konfiguriert um.

    Der Unterschied ist der ganze Punkt. Hier stand ein `if _configured: return`,
    und damit hatte `EFV_MCP_LOG_LEVEL` keine Wirkung mehr: `get_logger` auf
    Modulebene in `client.py` und `_otel.py` laeuft schon waehrend
    `from .server import mcp` — also *bevor* `main()` ueberhaupt die Settings
    gelesen hat — und setzte den Level auf die Vorgabe `INFO`. Das spaetere
    `configure_logging(settings.log_level)` traf dann auf `_configured = True`
    und lief durch.

    Gemessen am 18.9.2026 auf dem damaligen Stand: `EFV_MCP_LOG_LEVEL=DEBUG`
    gesetzt, `settings.log_level` las `DEBUG`, der effektive Root-Level blieb
    `INFO`. Nichts wurde dabei rot — die Einstellung war schlicht wirkungslos,
    und mit ihr jede `debug`-Zeile des Servers.

    `logging.basicConfig` allein reicht zum Umkonfigurieren nicht: der Aufruf
    ist ein No-op, sobald der Root-Logger Handler hat. Der Level wird deshalb
    ausdruecklich gesetzt.
    """
    global _configured_level
    normalisiert = level.upper()
    if _configured_level == normalisiert:
        return

    numerisch = getattr(logging, normalisiert, logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=numerisch)
    logging.getLogger().setLevel(numerisch)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numerisch),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    _configured_level = normalisiert


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger; configures with defaults if needed."""
    if _configured_level is None:
        configure_logging()
    return structlog.get_logger(name)
