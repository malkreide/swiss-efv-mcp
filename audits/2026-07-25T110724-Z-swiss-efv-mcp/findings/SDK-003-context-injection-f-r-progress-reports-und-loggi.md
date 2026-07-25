## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- No `ctx: Context` parameter on any tool — grep for `Context|ctx` in src/ returned no matches.
- No `ctx.info()` / `ctx.report_progress()` / `ctx.warning()` calls anywhere.
- client.py:97-112 `_fetch_with_retry` sleeps `backoff_base**attempt` (2s, 4s, 8s in prod) across up to 4 attempts — a cold-cache fetch of the 5 MB budget file plus retries can exceed 2s, exactly the case the check flags for progress reporting.

### Gaps
- Tools performing network fetch + exponential-backoff retry (potential multi-second latency) provide no `ctx: Context` and emit no progress or log notifications to the client.
- Upstream errors are swallowed into status() (client.py:127-131) rather than surfaced via ctx.warning()/ctx.error().
- No print()/stdlib-logging misuse (neutral). Remediation: add `ctx: Context` to fetch-backed tools and emit ctx.info()/ctx.report_progress() around load().

### Remediation
Migrationsweg für ein langes Tool:

```diff
+ from mcp.server.fastmcp import Context

  @mcp.tool()
- async def export_all_records(format: str) -> dict:
-     records = await db.fetch_all()
-     for record in records:
-         await transform(record, format)
-     return {"count": len(records)}
+ async def export_all_records(format: str, ctx: Context) -> dict:
+     await ctx.info(f"Starting export in format={format}")
+     records = await db.fetch_all()
+     await ctx.info(f"Loaded {len(records)} records, transforming...")
+
+     transformed = []
+     for i, record in enumerate(records):
+         if i % 50 == 0:
+             await ctx.report_progress(
+                 progress=i,
+                 total=len(records),
+                 message=f"Transformed {i}/{len(records)}",
+             )
+         transformed.append(await transform(record, format))
+
+     await ctx.info(f"Export complete: {len(transformed)} records")
+     return {"count": len(transformed), "format": format}
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
