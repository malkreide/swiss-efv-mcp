## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-001
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- server.py:16,30 imports `from fastmcp import FastMCP` and builds `mcp = FastMCP("swiss-efv-mcp")` with NO `lifespan=` argument.
- No `@asynccontextmanager` / lifespan function anywhere in src/ (grep for lifespan|asynccontextmanager returned no matches).
- client.py:122-124 opens a FRESH `httpx.AsyncClient(...)` per `load()` call inside `async with` — the documented fail-pattern (new HTTP client per invocation, no lifespan-managed shared pool).
- server.py:31 `client = EFVClient()` is a module-level global holding only a TTL row-cache; the httpx connection pool is created and torn down on every uncached fetch, and there is no server-lifecycle cleanup.

### Gaps
- No FastMCP lifespan (@asynccontextmanager) initialising a shared httpx.AsyncClient before first request and closing it after last.
- httpx.AsyncClient is instantiated per load() rather than reused via server.state — no connection pooling across calls, leak-on-exception risk.
- Mitigating factor: 24h in-memory TTL cache means not every tool call re-opens a client, but on cache-miss/expiry the anti-pattern applies fully.
- Remediation: move httpx.AsyncClient into a lifespan and inject via ctx.fastmcp.state (or pass into EFVClient), close in finally.

### Remediation
Migrationsweg:

```diff
+ from contextlib import asynccontextmanager
+ import httpx
+
+ @asynccontextmanager
+ async def lifespan(server):
+     server.state.http = httpx.AsyncClient(timeout=30)
+     try:
+         yield
+     finally:
+         await server.state.http.aclose()
+
- mcp = FastMCP("zurich-opendata")
+ mcp = FastMCP("zurich-opendata", lifespan=lifespan)

  @mcp.tool()
- async def search(query: str):
-     async with httpx.AsyncClient() as client:
-         return (await client.get(f"https://api/{query}")).json()
+ async def search(query: str, ctx):
+     return (await ctx.fastmcp.state.http.get(f"https://api/{query}")).json()
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
