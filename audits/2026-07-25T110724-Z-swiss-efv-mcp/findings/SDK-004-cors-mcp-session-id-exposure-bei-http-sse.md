## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-004
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- Dual transport confirmed: __main__.py:25-28 runs `mcp.run(transport="sse")` for TRANSPORT in {sse, streamable-http} — SDK-004 applies_when dual/HTTP-SSE is satisfied.
- No CORS configuration anywhere: grep for CORS|cors|expose_headers|allow_origins in src/ returned no matches.
- __main__.py only sets mcp.settings.host/port then calls mcp.run — no CORSMiddleware, no cors_expose_headers=["Mcp-Session-Id"] passed to FastMCP.
- server.py:30 `FastMCP("swiss-efv-mcp")` receives no cors_origins / cors_expose_headers.

### Gaps
- `Access-Control-Expose-Headers: Mcp-Session-Id` is not configured, so browser-based cross-origin clients cannot read the session id and stateful SSE sessions break (server-side curl/stdio tests still pass — subtle failure).
- No `allow_origins` allowlist (env-driven) for the SSE transport.
- Note: default HOST=127.0.0.1 limits exposure, but the CORS gap remains whenever SSE is served to browser clients. Remediation: add CORSMiddleware with expose_headers/allow_headers including Mcp-Session-Id and an explicit ALLOWED_ORIGINS env list.

### Remediation
```diff
  from starlette.applications import Starlette
  from starlette.routing import Mount
+ from starlette.middleware import Middleware
+ from starlette.middleware.cors import CORSMiddleware

+ ALLOWED_ORIGINS = [
+     o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
+ ]
+
+ middleware = [
+     Middleware(
+         CORSMiddleware,
+         allow_origins=ALLOWED_ORIGINS,
+         allow_methods=["GET", "POST", "OPTIONS"],
+         allow_headers=["Content-Type", "Mcp-Session-Id", "Authorization"],
+         expose_headers=["Mcp-Session-Id"],
+         allow_credentials=True,
+     ),
+ ]
+
  app = Starlette(
      routes=[Mount("/", app=mcp.streamable_http_app())],
+     middleware=middleware,
  )
```

Plus Umgebungsvariable:

```bash
# .env (production)
ALLOWED_ORIGINS=https://app.schulamt.zh.ch,https://claude.ai
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
