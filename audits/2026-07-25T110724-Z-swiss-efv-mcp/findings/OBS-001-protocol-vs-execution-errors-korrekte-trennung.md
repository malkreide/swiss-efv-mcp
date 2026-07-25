## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- src/swiss_efv_mcp/server.py:190-248 — all @mcp.tool wrappers just `return (...).model_dump()`; no try/except, so any exception bubbles to FastMCP and becomes a JSON-RPC protocol error
- src/swiss_efv_mcp/client.py:114-136 — load() raises (line 131) when upstream is unreachable and no cache exists; an execution-level failure (Upstream unreachable) thus surfaces as a JSON-RPC error, not a tool result
- grep across src/ for `isError`/`mask_error_details` returned no matches — no execution-error channel with isError:true anywhere
- No standardized JSON-RPC error codes (-326xx / -320xx) used anywhere in src/

### Gaps
- No separation of protocol vs execution errors: upstream/data failures propagate as JSON-RPC errors instead of tool-result with isError:true
- LLM cannot distinguish 'connection broken' from 'try different parameters / retry later'
- No standardized error-code constants; no documented test for execution-error vs protocol-error paths
- Partial mitigation only: dump_status/StatusReport (server.py:175-184) offers a graceful-degradation health channel, and load() prefers stale cache over failing (client.py:129-130), but real tool failures still raise

### Remediation
```diff
+ from mcp.types import TextContent
+
  @mcp.tool()
  async def query_database(query: str) -> dict:
-     # FAIL: alle Exceptions werden zu JSON-RPC-Errors
-     conn = await asyncpg.connect(DATABASE_URL)
-     return {"rows": await conn.fetch(query)}
+     try:
+         conn = await asyncpg.connect(DATABASE_URL)
+         try:
+             rows = await conn.fetch(query)
+             return {"rows": [dict(r) for r in rows]}
+         finally:
+             await conn.close()
+     except asyncpg.PostgresSyntaxError as e:
+         # Execution Error: Query-Problem ist Aufgabe des LLMs zu lösen
+         return {
+             "isError": True,
+             "content": [TextContent(
+                 type="text",
+                 text=f"SQL syntax error: {str(e)}. Try simplifying the query."
+             )],
+         }
+     except asyncpg.PostgresConnectionError:
+         # Protocol-nahe: Server ist degraded
+         raise McpError(code=-32603, message="Database temporarily unavailable")
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
