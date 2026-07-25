## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- src/swiss_efv_mcp/client.py:79-149 — per-instance in-memory TTL cache (`_cache`, 24h) and `_last_error`; module-level singleton client in server.py:31 — all session/data state lives in pod memory
- grep for `redis|sticky|affinity|SessionStore|session_manager` across repo returned no matches — no shared-state session manager
- No railway.toml / render.yaml / docker-compose.yml / k8s manifest present (ls of repo root) — no sticky-session LB configuration

### Gaps
- Neither required pattern implemented: no edge-LB sticky sessions on Mcp-Session-Id, no Redis/shared-state session manager
- Horizontal scaling (multiple replicas) would break FastMCP SSE sessions on pod switch and fragment the per-instance cache
- No documented single-instance constraint to justify the absence

### Remediation
### Variante A: Sticky Sessions mit HAProxy

```haproxy
frontend mcp_frontend
    bind *:443 ssl crt /etc/ssl/server.pem
    mode http
    # Backend-Selection nach Mcp-Session-Id
    default_backend mcp_backend

backend mcp_backend
    mode http
    balance roundrobin
    stick-table type string len 64 size 200k expire 24h peers mycluster
    stick on hdr(Mcp-Session-Id)
    option httpchk GET /healthz
    server mcp1 10.0.1.1:8080 check
    server mcp2 10.0.1.2:8080 check
    server mcp3 10.0.1.3:8080 check
```

### Variante B: Redis-basierter Session-Manager

```python
# pyproject.toml
# dependencies = ["fastmcp", "redis>=5.0", "structlog"]

from contextlib import asynccontextmanager
from fastmcp import FastMCP
from redis.asyncio import Redis
import json

@asynccontextmanager
async def lifespan(app):
    redis_client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    app.state.session_store = redis_client
    try:
        yield
    finally:
        await redis_client.aclose()

mcp = FastMCP("zurich-opendata", lifespan=lifespan)
```

### Effort-Empfehlung

- **Variante A** schneller bei vorhandener LB-Infrastruktur (1–2 Tage)
- **Variante B** robuster langfristig, vermeidet Sticky-Session-Komplikationen (3–5 Tage)

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
