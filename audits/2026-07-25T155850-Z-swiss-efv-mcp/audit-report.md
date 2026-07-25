# MCP-Server Audit-Report — `swiss-efv-mcp`

**Audit-Datum:** 2026-07-25
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-efv-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 38 bestanden, 3 Findings dokumentiert (0 critical, 3 high, 0 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-efv-mcp` |
| Audit-Datum | 2026-07-25 |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 11 | 0 | 0 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 5 | 0 | 0 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 3 | 0 | 2 | 0 | 0 |
| SDK | 4 | 0 | 0 | 0 | 0 |
| SEC | 11 | 0 | 1 | 3 | 0 |
| **Total** | **38** | **0** | **3** | **3** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SEC-005 | SEC | high | partial |

**Gesamt:** 3 Findings

---

## 5. Detail-Findings

### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** in-remediation (partial) — accepted-risk / documented deferral
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **partial**. This is an accepted risk documented in an
ADR / `docs/roadmap.md`; the mitigation path is prescribed, not silently ignored.

### Evidence
- src/swiss_efv_mcp/client.py:79-149 — per-instance in-memory TTL cache (`_cache`, 24h) and `_last_error`; module-level singleton client in server.py:31 — all session/data state lives in pod memory
- grep for `redis|sticky|affinity|SessionStore|session_manager` across repo returned no matches — no shared-state session manager
- No railway.toml / render.yaml / docker-compose.yml / k8s manifest present (ls of repo root) — no sticky-session LB configuration
- [remediated] Accepted-risk documented in docs/adr/0002-scaling-and-deployment.md (single-instance; stateful LB deferred with explicit re-evaluation triggers).

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


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** in-remediation (partial) — accepted-risk / documented deferral
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **partial**. This is an accepted risk documented in an
ADR / `docs/roadmap.md`; the mitigation path is prescribed, not silently ignored.

### Evidence
- grep for `stick|hdr(Mcp-Session|affinity|upstream-hash` across repo returned no matches
- No haproxy.cfg / nginx.conf / ingress*.yaml present anywhere in the repo (no deploy/ or helm/ directory)
- No edge-LB layer exists to read the Mcp-Session-Id header
- [remediated] Covered by docs/adr/0002 — Mcp-Session-Id edge routing deferred for the single-instance deployment; re-evaluation triggers documented.
- [v0.3.0-bundle] ADR 0002 now includes a concrete Mcp-Session-Id sticky-session example (nginx/Ingress/Traefik) for the multi-replica case; single-instance stays stateless-per-request.

### Gaps
- No Mcp-Session-Id header-based routing at any LB layer (complements the SCALE-002 gap)
- If deployed with >1 replica behind a default LB, sessions would round-robin without affinity and collapse

### Remediation
Für K8s-Ingress (NGINX):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-ingress
  annotations:
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "mcp-route"
    nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"
spec:
  rules:
  - host: mcp.example.ch
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mcp-server
            port:
              number: 8080
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** in-remediation (partial) — accepted-risk / documented deferral
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4

### Observed Behavior
Check evaluated as **partial**. This is an accepted risk documented in an
ADR / `docs/roadmap.md`; the mitigation path is prescribed, not silently ignored.

### Evidence
- client.py:42,58,64,70 — hostnames are fixed trusted EFV constants, not user-controlled, so an attacker cannot introduce a rebinding domain
- client.py:122-123 — httpx default client, no custom transport, no DNS pinning; follow_redirects=True
- [remediated] Accepted-risk documented in docs/adr/0001-dns-pinning.md; no user-controlled host + egress allow-list neutralise the rebinding precondition.
- [v0.3.0-bundle] Accepted-risk ADR 0001; docs/network-egress.md now prescribes the network-layer mitigation (default-deny egress NetworkPolicy / egress-proxy allow-list) that supersedes code DNS-pinning.

### Gaps
- No DNS-Pinning: no getaddrinfo/ipaddress single-resolution logic (grep confirms neither symbol present in src/)
- httpx default performs implicit resolution with no pinned-IP reuse (TOCTOU window exists in principle)
- No SNI/Host-header preservation logic because no pinning implemented
- follow_redirects=True could follow a redirect to a rebound host without re-validation

### Remediation
### Schritt 1: HTTP-Client mit Custom Transport

```python
import httpx
import socket
import ipaddress

class PinnedTransport(httpx.AsyncHTTPTransport):
    """HTTPX Transport mit DNS-Pinning."""

    async def handle_async_request(self, request):
        url = request.url
        if url.scheme != "https":
            raise httpx.RequestError("Only HTTPS allowed")

        # Resolve einmalig
        loop = asyncio.get_event_loop()
        addrinfo = await loop.getaddrinfo(
            url.host, url.port, type=socket.SOCK_STREAM
        )
        resolved_ip = addrinfo[0][4][0]

        # Range-Check
        ip = ipaddress.ip_address(resolved_ip)
        for blocked in BLOCKED_NETWORKS:
            if ip in blocked:
                raise httpx.RequestError(f"Blocked IP: {ip}")

        # URL mit gepinnter IP, aber Host-Header bleibt
        pinned_url = httpx.URL(str(url).replace(url.host, resolved_ip, 1))
        new_request = httpx.Request(
            method=request.method,
            url=pinned_url,
            headers=httpx.Headers(request.headers),
            content=request.content,
            extensions=request.extensions,
        )
        new_request.headers["Host"] = url.host
        # SNI bleibt durch URL-Hostname (httpx interner default)
        return await super().handle_async_request(new_request)


# Verwendung
async with httpx.AsyncClient(transport=PinnedTransport()) as client:
    response = await client.get("https://api.external.com/data")
```

### Schritt 2: Alternative — Egress-Proxy

Wenn Custom-Transport zu komplex: Stripe Smokescreen als Sidecar erledigt DNS-Pinning automatisch.

```yaml
# docker-compose.yml
services:
  smokescreen:
    image: stripe/smokescreen:latest
    command: ["--listen-ip", "127.0.0.1", "--listen-port", "4750"]

  mcp-server:
    image: malkreide/mcp-server
    environment:
      HTTPS_PROXY: http://smokescreen:4750
```

```python
# Im Code: einfach Proxy nutzen
async with httpx.AsyncClient(proxy="http://localhost:4750") as client:
    return await client.get(url)
```

### Schritt 3: Tests

Wie im Mock-Beispiel oben. Plus Integration-Test, der nachweist dass die SSRF-Test-Suite (SEC-004 Modus 3) auch mit Rebinding-Versuchen besteht.

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SCALE-002** (high, partial)
2. **SCALE-003** (high, partial)
3. **SEC-005** (high, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-07-25` |


_Generated by tools/build_report.py — do not edit by hand._
