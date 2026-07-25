# MCP-Server Audit-Report — `swiss-efv-mcp`

**Audit-Datum:** 2026-07-25
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-efv-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 36 bestanden, 5 Findings dokumentiert (0 critical, 4 high, 1 medium, 0 low). Production-Readiness: erreicht.

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
| ARCH | 10 | 0 | 1 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 5 | 0 | 0 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 3 | 0 | 2 | 0 | 0 |
| SDK | 4 | 0 | 0 | 0 | 0 |
| SEC | 10 | 0 | 2 | 3 | 0 |
| **Total** | **36** | **0** | **5** | **3** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-012 | ARCH | medium | partial |

**Gesamt:** 5 Findings

---

## 5. Detail-Findings

### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior
Check evaluated as **partial** after the backlog cycle. Remaining `partial`
items are documented deferrals / accepted-risk (see docs/roadmap.md, docs/adr/).

### Evidence
- CHANGELOG.md:1-6 — present and in Keep-a-Changelog format with SemVer reference; [Unreleased] and [0.1.0] sections maintained
- .github/dependabot.yml:3-11 — monthly pip updates active (comment notes it keeps the mcp/fastmcp SDK current), satisfying the SDK-update-discipline criterion
- README.md:222-228 — a dedicated 'MCP Protocol Version' section exists and notes protocol-relevant bumps go in CHANGELOG.md
- [backlog-cycle] MCP protocol version negotiated by FastMCP at initialize; kept current via Dependabot; explicit pinning deferred (documented in docs/roadmap.md).

### Gaps
- protocolVersion is NOT explicitly pinned in code — grep for protocolVersion|protocol_version|PROTOCOL_VERSION in src/ returns nothing; README.md:224-228 states the version is 'negotiated at the initialize handshake by FastMCP' rather than pinned, which is exactly the Fail-Pattern (SDK default, can shift on update)
- No documented Breaking-Change / compatibility-window policy tied to a specific spec version; CHANGELOG has no spec-version-bump entries yet (only 0.1.0)

### Remediation
### Schritt 1: protocolVersion pinnen

```diff
+ from importlib.metadata import version

  mcp = FastMCP(
      name="zh-education-mcp",
+     protocol_version="2025-06-18",
  )
```

### Schritt 2: CHANGELOG initialisieren

Wenn nicht vorhanden, mit Template starten und retroaktiv Major-Versionen dokumentieren (mindestens letzte 3).

### Schritt 3: Dependabot konfigurieren

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
```

### Schritt 4: Quartalsweise Spec-Review

Im Audit-Tracker (Notion) oder GitHub Issues ein recurring Reminder für quartalsweise Spec-Velocity-Review:

- Was hat sich an der MCP-Spec geändert seit letztem Release?
- Welche Server müssen ihre `protocolVersion` aktualisieren?
- Gibt es Compliance-relevante Spec-Änderungen?

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **partial** after the backlog cycle. Remaining `partial`
items are documented deferrals / accepted-risk (see docs/roadmap.md, docs/adr/).

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
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **partial** after the backlog cycle. Remaining `partial`
items are documented deferrals / accepted-risk (see docs/roadmap.md, docs/adr/).

### Evidence
- grep for `stick|hdr(Mcp-Session|affinity|upstream-hash` across repo returned no matches
- No haproxy.cfg / nginx.conf / ingress*.yaml present anywhere in the repo (no deploy/ or helm/ directory)
- No edge-LB layer exists to read the Mcp-Session-Id header
- [remediated] Covered by docs/adr/0002 — Mcp-Session-Id edge routing deferred for the single-instance deployment; re-evaluation triggers documented.

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
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4

### Observed Behavior
Check evaluated as **partial** after the backlog cycle. Remaining `partial`
items are documented deferrals / accepted-risk (see docs/roadmap.md, docs/adr/).

### Evidence
- client.py:42,58,64,70 — hostnames are fixed trusted EFV constants, not user-controlled, so an attacker cannot introduce a rebinding domain
- client.py:122-123 — httpx default client, no custom transport, no DNS pinning; follow_redirects=True
- [remediated] Accepted-risk documented in docs/adr/0001-dns-pinning.md; no user-controlled host + egress allow-list neutralise the rebinding precondition.

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


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-022
**PDF-Reference:** Anhang B4

### Observed Behavior
Check evaluated as **partial** after the backlog cycle. Remaining `partial`
items are documented deferrals / accepted-risk (see docs/roadmap.md, docs/adr/).

### Evidence
- server.py:190-241 — 4 of 5 tools carry a topic prefix (fiscal_headline, fiscal_budget_breakdown, fiscal_by_institution, fiscal_list_dimensions), reducing collision risk
- SECURITY.md:38-41 — tool definitions are version-controlled, authored in-repo, PR-reviewed, with no dynamic/remote registration (partial rug-pull mitigation)
- server.py:245 — dump_status has no prefix at all; no server-identity namespace (e.g. swiss_efv__) is used
- [backlog-cycle] Server-identity namespace via MCP Registry name io.github.malkreide/swiss-efv-mcp; renaming unprefixed dump_status deferred post-0.2.0 to avoid a breaking change (documented).

### Gaps
- No server-identity namespace prefix: 'fiscal_' is a topic prefix, not a <server>__ identity prefix, and is inconsistent (dump_status unprefixed) — cross-server shadowing not structurally prevented
- No tool-definition hash snapshot generated at release: publish.yml has no sha256/tool-hashes.json step (grep of CHANGELOG/server.json finds no hash/namespace mention)
- No CHANGELOG discipline for tool-definition changes / re-approval hints

### Remediation
### Schritt 1: Namespace-Audit

Server-Identity festlegen — typisch der Repo-Name als snake_case-Präfix:

| Repo | Namespace |
|---|---|
| `zh-education-mcp` | `zh_education` |
| `zurich-opendata-mcp` | `zurich_opendata` |
| `parlament-mcp` | `parlament_ch` |

### Schritt 2: Tool-Renaming

```diff
- @mcp.tool()
- async def search(query: str): ...
+ @mcp.tool(name="zh_education__search")
+ async def search(query: str): ...
```

Bei Renaming: Major-Version-Bump, da Tool-Namen Breaking-Changes sind.

### Schritt 3: Hash-Snapshot-Workflow

CI-Step wie im Pass-Pattern Modus 2. `tool-hashes.json` als Artefakt im Release.

### Schritt 4: Bei Update-Disziplin (Synergie zu ARCH-012)

CHANGELOG-Template um «Tool Definition Changes»-Sektion erweitern:

```markdown

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SCALE-002** (high, partial)
2. **SCALE-003** (high, partial)
3. **SEC-005** (high, partial)
4. **SEC-022** (high, partial)
5. **ARCH-012** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-07-25` |


_Generated by tools/build_report.py — do not edit by hand._
