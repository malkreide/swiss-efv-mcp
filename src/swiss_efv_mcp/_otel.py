"""Optional OpenTelemetry tracing (OBS-006).

Off by default. Enable with ``EFV_MCP_OTEL_ENABLED=1`` and install the optional
extra: ``pip install swiss-efv-mcp[otel]``. Export is configured through the
standard ``OTEL_EXPORTER_OTLP_ENDPOINT`` / ``OTEL_*`` environment variables.

If the extra is not installed, :func:`setup_otel` logs a warning and no-ops, so
the default install never pulls in the OpenTelemetry stack.
"""

from __future__ import annotations

from .logging_config import get_logger

_log = get_logger(__name__)
_configured = False


def setup_otel(enabled: bool) -> bool:
    """Best-effort OpenTelemetry setup. Returns True if tracing was configured."""
    global _configured
    if not enabled or _configured:
        return _configured
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        _log.warning(
            "otel_requested_but_not_installed",
            hint="pip install 'swiss-efv-mcp[otel]'",
        )
        return False

    provider = TracerProvider(resource=Resource.create({"service.name": "swiss-efv-mcp"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    # Trace every outbound httpx call (the only egress this server makes).
    HTTPXClientInstrumentor().instrument()
    _configured = True
    _log.info("otel_enabled", service="swiss-efv-mcp")
    return True
