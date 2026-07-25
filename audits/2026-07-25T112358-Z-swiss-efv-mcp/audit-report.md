# MCP-Server Audit-Report — `swiss-efv-mcp`

**Audit-Datum:** 2026-07-25
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-efv-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 26 bestanden, 15 Findings dokumentiert (1 critical, 7 high, 7 medium, 0 low). Production-Readiness: erreicht.

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
| ARCH | 8 | 0 | 3 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 4 | 1 | 0 | 0 | 0 |
| OPS | 1 | 0 | 2 | 0 | 0 |
| SCALE | 2 | 1 | 2 | 0 | 0 |
| SDK | 2 | 1 | 1 | 0 | 0 |
| SEC | 8 | 0 | 4 | 3 | 0 |
| **Total** | **26** | **3** | **12** | **3** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-004 | SEC | critical | partial |
| OPS-001 | OPS | high | partial |
| OPS-003 | OPS | high | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-007 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-006 | OBS | medium | fail |
| SCALE-006 | SCALE | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | fail |

**Gesamt:** 15 Findings

---

## 5. Detail-Findings

### ARCH-002

## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-002
**PDF-Reference:** Sec 2.2

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- src/swiss_efv_mcp/server.py:198-247 — every tool docstring is a multi-line description well above the 100-char median threshold and includes parameter guidance and enum hints
- src/swiss_efv_mcp/server.py:198-201 — fiscal_headline description names valid values ('saldo','einnahmen',...) and points to fiscal_list_dimensions (implicit use-case guidance)

### Gaps
- No structured XML-style tags present anywhere: grep for <use_case>|<important_notes>|<example> in src/ returns nothing, so the ≥80%-use_case-tag criterion is unmet
- Descriptions lack explicit <important_notes> for caveats (e.g. the 2022/2023 accounting-model seam is only surfaced at runtime via a 'note' field, not in the tool description)

### Remediation
```diff
  @mcp.tool(
      name="searchEducationStats",
-     description="Search education statistics."
+     description=(
+         "Sucht in den städtischen Bildungsstatistiken nach Kennzahlen "
+         "(Klassengrösse, Lehrer-Schüler-Verhältnis, Anteil DaZ, etc.).\n\n"
+         "<use_case>Politische / journalistische Recherche, "
+         "Schulamts-interne Reportings, Pädagogik-Analysen.</use_case>\n\n"
+         "<important_notes>Daten werden quartalsweise aktualisiert. "
+         "Personendaten sind nicht abrufbar — nur aggregierte "
+         "Kennzahlen.</important_notes>"
+     ),
  )
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- src/swiss_efv_mcp/server.py:71-73,148-153 — empty searches never return a bare [] or 'No results' string; they return a structured Pydantic envelope (HeadlineSeries/InstitutionSeries) carrying source+provenance even when points is empty
- src/swiss_efv_mcp/server.py:237-241 + 156-172 — a dedicated fiscal_list_dimensions tool exists so the model can discover valid dimension values instead of guessing after an empty hit
- src/swiss_efv_mcp/server.py:175-184,244-248 — dump_status is explicitly designed to 'never return empty silently' and reports degradation with an actionable retry hint

### Gaps
- No match_type field (exact/fuzzy/none) on any search response — server.py:71-73 (headline) and 148-153 (institution) return empty points with no match_type marker
- No fuzzy fallback or suggestion mechanism and no actionable per-tool 'note' on an empty result set; an empty fiscal_headline/fiscal_by_institution call yields empty points with no pointer back to fiscal_list_dimensions
- budget_impl only sets a 'note' for the accounting-model seam (server.py:108-110), not for the zero-results case

### Remediation
```diff
  @mcp.tool()
  async def find_school(name: str) -> list:
      results = await db.find(name)
-     if not results:
-         return []
+     if not results:
+         fuzzy = await db.find_fuzzy(name, threshold=0.7)
+         suggestions = await db.popular_school_names_starting_with(name[:3])
+         return {
+             "results": fuzzy[:5],
+             "match_type": "fuzzy" if fuzzy else "none",
+             "note": (
+                 f"Keine exakten Treffer für '{name}'. "
+                 f"{'Ähnliche Schulen aufgeführt.' if fuzzy else ''} "
+                 f"Häufige Schulnamen: {', '.join(suggestions[:5])}"
+             ),
+         }
      return {"results": results, "match_type": "exact"}
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- CHANGELOG.md:1-6 — present and in Keep-a-Changelog format with SemVer reference; [Unreleased] and [0.1.0] sections maintained
- .github/dependabot.yml:3-11 — monthly pip updates active (comment notes it keeps the mcp/fastmcp SDK current), satisfying the SDK-update-discipline criterion
- README.md:222-228 — a dedicated 'MCP Protocol Version' section exists and notes protocol-relevant bumps go in CHANGELOG.md

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


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10

### Observed Behavior
Check evaluated as **fail** after the hardening commit.

### Evidence
- grep for `opentelemetry|otel|start_as_current_span` across src/ returned no matches
- pyproject.toml:26-30 — no opentelemetry-* packages in dependencies
- No TracerProvider/OTLP exporter/HTTPX auto-instrumentation and no OTEL_* env config anywhere in repo (Dockerfile, README, workflows)

### Gaps
- Cloud-deployable (Railway/Render) but no distributed tracing at all
- No per-tool-call spans, no backend-latency child spans, no OTLP endpoint via env var
- Slow-tool / user-behavior / backend-bottleneck forensics not possible

### Remediation
### Schritt 1: SDK-Installation

```toml
# pyproject.toml
[project.dependencies]
"opentelemetry-api" = "^1.21"
"opentelemetry-sdk" = "^1.21"
"opentelemetry-exporter-otlp" = "^1.21"
"opentelemetry-instrumentation-httpx" = "^0.42b0"
```

### Schritt 2: Setup-Modul

```python
# src/server_name/observability.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
# ...

def setup_tracing():
    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "schulamt-mcp"),
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
```

### Schritt 3: Decorator anwenden

`@traced_tool` als Standard auf alle Tool-Decorators stacken.

### Schritt 4: OTLP-Backend wählen

Für Schulamt-Kontext: Datadog (DSG-konform mit `DD_SITE=datadoghq.eu`), Grafana Tempo (selbst-gehostet, OpenBao-Compatible), oder Honeycomb (EU-Region).

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### OPS-001

## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** OPS-001
**PDF-Reference:** Anhang C1

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- tests/test_client.py:1-3 imports respx and uses @respx.mock on 10 offline unit tests covering happy-path, NA-cleaning, year/household filter, 503-retry-recovery, timeout-raises, degraded-status, budget level filter, institution filter, dimensions-distinct, cache-hit.
- tests/test_live.py:12 `pytestmark = pytest.mark.live` marks all live tests; run via `pytest -m live`.
- pyproject.toml:55-57 registers the `live` marker; :32-38 dev extras include respx>=0.21, pytest, pytest-asyncio.
- .github/workflows/ci.yml:30 runs `pytest tests/ -m "not live"` (live excluded) plus ruff, on Python 3.11/3.12/3.13.

### Gaps
- Per-tool live coverage incomplete: test_live.py exercises headline, dimensions, budget but NOT `fiscal_by_institution` (institution_impl) nor `dump_status` (status_impl).
- Does not meet the check's ‘>=5 unit tests per tool’ bar (10 unit tests spread across 5 tools) — though core paths (happy/error/edge) are covered.
- No separate nightly/scheduled live-test workflow (live runs are manual only); no coverage measurement (pytest-cov not a dev dep, no --cov in CI).
- No auth/credentials to leak (public OGD) — the test-key concern is N/A here.

### Remediation
### Schritt 1: pyproject.toml-Marker registrieren

```toml
[tool.pytest.ini_options]
markers = [
    "live: tests against real APIs (manual, nightly only)",
]
```

### Schritt 2: respx als Dev-Dependency

```toml
[project.optional-dependencies]
dev = [
    "pytest >= 7.4",
    "pytest-asyncio >= 0.21",
    "pytest-cov >= 4.1",
    "respx >= 0.20",
]
```

### Schritt 3: Unit-Test-Suite aufbauen

Pro Tool mindestens drei Tests:
- Happy-Path (200, expected schema)
- Error-Path (4xx/5xx)
- Edge-Case (leere Antwort, malformed input)

### Schritt 4: CI-Workflow updaten

`.github/workflows/test.yml`:

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -m "not live" --cov=src
```

### Schritt 5: Nightly-Live-Workflow

Wie im Pass-Pattern Modus 4.

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- README.md:208-220 ‘Project Phase’ explicitly declares Phase 1 (read-only) with a status table (Phase 1 ✅ current, Phase 2 detail cubes planned, Phase 3 none planned) and states a re-audit is required before any write-capable tool.
- Phase matches tool annotations: all five tools are read-only (README.md:114-116, 178-179 ‘Read-only by design’; server.py tools only call HTTP GET via client.load()); no destructive/write tools exist.
- README.de.md:212 ‘Projektphase’ mirrors the phase declaration bilingually.
- CHANGELOG references Phase-2 deferral of detail cubes (CHANGELOG.md:63-64).

### Gaps
- No dedicated `docs/roadmap.md` file (docs/ directory does not exist); the roadmap lives only as an inline README table — the check's Modus 3 wants a roadmap file with phase-specific tasks.
- Phase-1 prerequisite artifacts named in the check (ISDS-Klassifikation, DSG-Verarbeitungsverzeichnis, recorded audit-run) are not present/linked — though several are arguably N/A for a private non-governmental project over public data.
- Core phase discipline (explicit declaration + read-only tool match) is satisfied; the formal roadmap-file and prerequisite-doc scaffolding is missing.

### Remediation
### Schritt 1: Phase-Audit pro Server

Pro Server im Portfolio:

| Frage | Antwort |
|---|---|
| Hat der Server destruktive Tools? | ja → mindestens Phase 3 |
| Hat der Server Semantic Layer / Federation? | ja → mindestens Phase 2 |
| Sonst | Phase 1 |

### Schritt 2: Phase-Sektion ins README

Mit Status-Tabelle wie im Pass-Pattern Modus 1.

### Schritt 3: Roadmap erstellen

Mit Phase-Voraussetzungen als Tasks. Falls aktueller Server in Phase 2 oder 3 ist und Phase-1-Voraussetzungen fehlen: Findings im Audit-Tracker dokumentieren, retroaktiv schliessen.

### Schritt 4: Phase-Gate als Notion-Workflow

In Notion-Audit-Tracker-Schema (`a2736a65-...`) ein Feld «Phase» (Single-Select: 1, 2, 3) mit klaren Übergangs-Anforderungen.

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

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
Check evaluated as **partial** after the hardening commit.

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


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-006
**PDF-Reference:** Sec 5.3

### Observed Behavior
Check evaluated as **fail** after the hardening commit.

### Evidence
- No k8s/helm manifest, no docker-compose.yml, no railway.toml/render.yaml present in repo (ls of root) — nowhere to set memory/cpu limits
- Dockerfile has no `ulimit`/nofile configuration and no resource constraints
- grep of README for memory/cpu/resource limits found no documented limits (README.md:90-102 lists only TRANSPORT/HOST/PORT)

### Gaps
- No explicit memory limit, CPU limit, or FD limit defined or documented for the cloud deployment
- Relevant here because the in-memory dump cache can grow (multiple CSVs, up to ~5 MB each) — an unbounded pod could OOM the host
- No restart-policy / OOM-behavior documentation

### Remediation
Für Railway: in der Web-UI unter Project Settings → Resources die Limits setzen.

Für Docker-Compose-Production:

```yaml
services:
  mcp:
    image: malkreide/mcp-server:v0.1.0
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    ulimits:
      nofile:
        soft: 4096
        hard: 8192
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- pyproject.toml:29 pins `pydantic>=2.7` (Pydantic v2).
- models.py:19-21 defines an `Envelope(BaseModel)` with `source` (default=ATTRIBUTION) + `provenance: Provenance` where `Provenance = Literal["dump","cached"]` (models.py:16) — consistent envelope, Literal enum, no mutable defaults (uses Field(default=...)).
- All five response models (HeadlineSeries, BudgetBreakdown, InstitutionSeries, Dimensions extend Envelope; StatusReport carries source) are proper Pydantic v2 BaseModels with typed fields.
- The *_impl functions have correct model return annotations (e.g. server.py:37-44 `-> HeadlineSeries`).

### Gaps
- The @mcp.tool wrappers are annotated `-> dict` and return `.model_dump()` (server.py:197/204, 213/218, 227/233, 237/241, 245/248), so FastMCP receives a plain dict and does NOT expose the rich Pydantic output schema in tools/list — the model-level schema benefit is discarded at the tool boundary.
- No `count` / `match_type` fields on search-style envelopes (minor; envelope has source+provenance+results-equivalent lists).
- Remediation: annotate tools to return the Pydantic model directly (e.g. `-> HeadlineSeries`) and return the model instance instead of `.model_dump()`.

### Remediation
```diff
+ from pydantic import BaseModel, Field
+ from typing import Literal
+
+ class SearchResponse(BaseModel):
+     source: str = Field(default="DataSource Name — CC BY 4.0")
+     provenance: Literal["live_api", "cached", "weekly_dump"]
+     results: list[dict]
+     count: int

  @mcp.tool()
- async def search(query: str):
-     results = await api.search(query)
-     return {"results": results, "count": len(results)}
+ async def search(query: str, ctx) -> SearchResponse:
+     results = await api.search(query)
+     return SearchResponse(
+         provenance="live_api",
+         results=results,
+         count=len(results),
+     )
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **fail** after the hardening commit.

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


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- client.py:41-74 — all three dataset URLs are hardcoded module constants (https:// on data.finance.admin.ch / efv.admin.ch); no user input ever builds a URL, so the primary SSRF vector is structurally absent
- client.py:122-123 — httpx.AsyncClient uses default TLS verification (never disabled) but follow_redirects=True
- SECURITY.md:22 & README.md:180-182 — documents fixed hardcoded egress, 'no SSRF surface'
- [remediated] client.py enforces https scheme + host allow-list before each request (improved); follow_redirects still on and no IP-literal blocklist — residual.

### Gaps
- No explicit HTTPS scheme validation before requests (no urlparse scheme check)
- No resolved-IP blocklist (169.254.169.254, private/loopback/link-local ranges never checked)
- No DNS pinning / getaddrinfo guard
- follow_redirects=True means an upstream 3xx could redirect the fetch to an internal/metadata IP with no post-resolution IP check — residual SSRF-via-redirect gap

### Remediation
Volles Pattern oben. Zusätzlich für Defense-in-Depth:

### Container-Level Egress-Filtering

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-server-egress
spec:
  podSelector:
    matchLabels:
      app: mcp-server
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
              - 169.254.0.0/16
              - 127.0.0.0/8
      ports:
        - protocol: TCP
          port: 443
```

### IMDSv2 statt IMDSv1 (AWS-spezifisch)

Falls auf AWS deployed: IMDSv2 mit Hop-Limit 1 erzwingen (verhindert SSRF auch bei Code-Bug).

```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxx \
  --http-tokens required \
  --http-put-response-hop-limit 1
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
Check evaluated as **partial** after the hardening commit.

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


### SEC-007

## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-007
**PDF-Reference:** Sec 4.5

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- Dockerfile:12 — useradd --uid 10001 non-root user (UID >= 10000)
- Dockerfile:14 — USER 10001 set before ENTRYPOINT
- Dockerfile:4-10 — multi-stage build (build stage + slim runtime)

### Gaps
- No readOnlyRootFilesystem (no k8s manifests / no runtime read-only enforcement)
- No capabilities drop (CapDrop ALL) and no seccomp profile referenced
- No Kubernetes SecurityContext (runAsNonRoot/allowPrivilegeEscalation:false) — no k8s/helm manifests in repo
- No container security scan (Trivy/Snyk) step in CI

### Remediation
### Schritt 1: Dockerfile-User anpassen

Wie im Pass-Pattern oben.

### Schritt 2: Kubernetes-SecurityContext setzen

Im Helm-Chart oder Deployment-Manifest.

### Schritt 3: Tests gegen Privileg-Eskalation

```python
def test_container_runs_as_non_root():
    result = subprocess.run(
        ["docker", "exec", CONTAINER_ID, "id", "-u"],
        capture_output=True, text=True,
    )
    assert int(result.stdout.strip()) >= 10000

def test_filesystem_read_only():
    result = subprocess.run(
        ["docker", "exec", CONTAINER_ID, "touch", "/etc/test"],
        capture_output=True, text=True,
    )
    assert "Read-only" in result.stderr or result.returncode != 0
```

### Schritt 4: CI-Check via Trivy / Snyk

```yaml
- name: Container security scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: malkreide/mcp-server:${{ github.sha }}
    severity: CRITICAL,HIGH
    exit-code: 1
```

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
Check evaluated as **partial** after the hardening commit.

### Evidence
- server.py:190-241 — 4 of 5 tools carry a topic prefix (fiscal_headline, fiscal_budget_breakdown, fiscal_by_institution, fiscal_list_dimensions), reducing collision risk
- SECURITY.md:38-41 — tool definitions are version-controlled, authored in-repo, PR-reviewed, with no dynamic/remote registration (partial rug-pull mitigation)
- server.py:245 — dump_status has no prefix at all; no server-identity namespace (e.g. swiss_efv__) is used

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

1. **SEC-004** (critical, partial)
2. **OPS-001** (high, partial)
3. **OPS-003** (high, partial)
4. **SCALE-002** (high, partial)
5. **SCALE-003** (high, partial)
6. **SEC-005** (high, partial)
7. **SEC-007** (high, partial)
8. **SEC-022** (high, partial)
9. **ARCH-002** (medium, partial)
10. **ARCH-003** (medium, partial)
11. **ARCH-012** (medium, partial)
12. **OBS-006** (medium, fail)
13. **SCALE-006** (medium, fail)
14. **SDK-002** (medium, partial)
15. **SDK-003** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-07-25` |


_Generated by tools/build_report.py — do not edit by hand._
