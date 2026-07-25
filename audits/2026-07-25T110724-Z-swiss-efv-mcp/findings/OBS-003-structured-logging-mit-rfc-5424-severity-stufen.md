## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** OBS-003
**PDF-Reference:** Sec 6.3

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- pyproject.toml:26-30 — dependencies are only fastmcp, httpx, pydantic; no structlog/pino/loguru
- grep for `import logging|structlog|loguru` across src/ returned no matches — no logging framework of any kind
- No logger.info/warning/error calls, no JSON/logfmt output, no bound per-tool context (session_id/correlation_id) anywhere in src/

### Gaps
- No structured logger dependency
- No severity-level logging (RFC 5424) at all
- No correlation-id / per-tool-call bound context — multi-step workflows not traceable

### Remediation
```diff
- import logging
- logger = logging.getLogger(__name__)
+ import structlog
+ logger = structlog.get_logger("mcp.server")

  @mcp.tool()
  async def search(query: str, ctx):
-     logger.info(f"Searching for {query}")
-     result = await api.search(query)
-     logger.info(f"Got {len(result)} results")
+     log = logger.bind(tool="search", query=query, session=ctx.session_id)
+     log.info("tool_invoked")
+     result = await api.search(query)
+     log.info("tool_succeeded", count=len(result))
      return result
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
