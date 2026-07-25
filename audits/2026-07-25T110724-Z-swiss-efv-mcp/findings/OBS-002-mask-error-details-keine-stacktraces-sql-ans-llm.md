## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** OBS-002
**PDF-Reference:** Sec 6.2

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- src/swiss_efv_mcp/server.py:30 — `mcp = FastMCP("swiss-efv-mcp")`; no `mask_error_details=True` set
- src/swiss_efv_mcp/client.py:128 — `self._last_error[key] = f"{type(exc).__name__}: {exc}"` stores the raw upstream exception text
- src/swiss_efv_mcp/client.py:147 + server.py:175-184 — that raw last_error string is returned through status()/StatusReport and reaches the model via the dump_status tool result
- grep for `traceback|format_exc|sys.exc_info` across src/ returned no matches — no stacktrace leakage
- No credentials/tokens in play (no auth); upstream URLs already public in code/README

### Gaps
- mask_error_details is not enabled on the FastMCP instance (default behavior is version-dependent)
- Raw upstream exception text (`{ExceptionType}: {message}`) is surfaced into the LLM context via dump_status rather than confined to a server log
- Low actual disclosure severity (no stacktrace, no SQL, no secrets, read-only public data) but hygiene criteria not met

### Remediation
```diff
  mcp = FastMCP(
      "server",
+     mask_error_details=True,
  )

  @mcp.tool()
  async def search(query: str):
      try:
          return await db.search(query)
-     except Exception as e:
-         return {"error": str(e), "traceback": traceback.format_exc()}
+     except UserInputError as e:
+         return {"isError": True, "content": [
+             TextContent(type="text", text=f"Invalid input: {e.user_message}")
+         ]}
+     except Exception:
+         logger.exception("Unhandled error in search tool")
+         raise  # mask_error_details greift, generische Message ans LLM
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
