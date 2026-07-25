# MCP-Server Audit-Report — `swiss-efv-mcp`

**Audit-Datum:** 2026-07-25
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-efv-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 17 bestanden, 24 Findings dokumentiert (1 critical, 14 high, 9 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: ARCH-009, OBS-001, SCALE-002, SCALE-003, SDK-001, SDK-004.

**Production-Readiness:** NO

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
| ARCH | 7 | 1 | 3 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 1 | 3 | 1 | 0 | 0 |
| OPS | 1 | 0 | 2 | 0 | 0 |
| SCALE | 1 | 3 | 1 | 0 | 0 |
| SDK | 0 | 3 | 1 | 0 | 0 |
| SEC | 6 | 0 | 6 | 3 | 0 |
| **Total** | **17** | **10** | **14** | **3** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-004 | SEC | critical | partial |
| ARCH-009 | ARCH | high | fail |
| OBS-001 | OBS | high | fail |
| OBS-002 | OBS | high | partial |
| OPS-001 | OPS | high | partial |
| OPS-003 | OPS | high | partial |
| SCALE-002 | SCALE | high | fail |
| SCALE-003 | SCALE | high | fail |
| SDK-001 | SDK | high | fail |
| SDK-004 | SDK | high | fail |
| SEC-005 | SEC | high | partial |
| SEC-007 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-003 | OBS | medium | fail |
| OBS-006 | OBS | medium | fail |
| SCALE-004 | SCALE | medium | partial |
| SCALE-006 | SCALE | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | fail |

**Gesamt:** 24 Findings

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
Check evaluated as **partial** against the current code.

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
Check evaluated as **partial** against the current code.

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


### ARCH-009

## Finding: ARCH-009 — Tool Annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-009
**PDF-Reference:** Anhang A5

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- src/swiss_efv_mcp/server.py:190,207,221,236,244 — all 5 tools use bare @mcp.tool() with no annotations argument; grep for readOnlyHint|destructiveHint|idempotentHint|openWorldHint in src/ returns nothing
- README.md:114-115 — read-only nature is stated in prose ('All tools are read-only by design') but is not encoded as machine-readable ToolAnnotations the host can consume

### Gaps
- No tool sets explicit annotations, so hosts must treat every call pessimistically (confirmation fatigue); the 'all tools have explicit annotations' criterion fails outright
- Remediation: add annotations={'readOnlyHint': True, 'idempotentHint': True, 'openWorldHint': True} (tools do reach external EFV hosts) to all 5 read-only tools, and add an annotations overview table to the README

### Remediation
### Schritt 1: Annotations-Inventar

Pro Tool eine Tabelle mit den vier Hints. Wenn unsicher: per Default konservativ (alles `false`/weggelassen impliziert «kann gefährlich sein»).

### Schritt 2: Decorator-Helper

```python
from typing import Literal

def read_only_tool(*args, **kwargs):
    """Shortcut für read-only Tools mit konsistenten Annotations."""
    annotations = kwargs.pop("annotations", {})
    annotations.update({
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    })
    kwargs["annotations"] = annotations
    return mcp.tool(*args, **kwargs)


@read_only_tool()
async def search_motions(args, ctx):
    ...
```

### Schritt 3: CI-Test gegen Drift

```python
def test_destructive_tools_have_destructive_hint():
    """Tools mit delete/create/update im Namen müssen destructiveHint setzen."""
    suspicious_prefixes = ("delete_", "create_", "update_", "remove_")
    for tool_name, tool in mcp.tools.items():
        if any(tool_name.startswith(p) for p in suspicious_prefixes):
            annotations = tool.annotations or {}
            assert annotations.get("readOnlyHint") is not True, (
                f"{tool_name} suggests write but is marked readOnlyHint"
            )
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior
Check evaluated as **partial** against the current code.

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


### OBS-001

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


### OBS-002

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


### OBS-003

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


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10

### Observed Behavior
Check evaluated as **fail** against the current code.

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
Check evaluated as **partial** against the current code.

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
Check evaluated as **partial** against the current code.

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


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- grep for `stick|hdr(Mcp-Session|affinity|upstream-hash` across repo returned no matches
- No haproxy.cfg / nginx.conf / ingress*.yaml present anywhere in the repo (no deploy/ or helm/ directory)
- No edge-LB layer exists to read the Mcp-Session-Id header

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


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-004
**PDF-Reference:** Sec 5.3

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- Dockerfile:4 and :10 — two FROM statements (multi-stage build); both use python:3.12-slim base
- Dockerfile:4 — first stage named `AS build`; Dockerfile:10 — second (runtime) stage is NOT named
- Dockerfile:11-14 — non-root user created (uid 10001) and `USER 10001` set
- Dockerfile:8 — `pip install --no-cache-dir --prefix=/install`; Dockerfile:21 EXPOSE 8000
- No HEALTHCHECK directive anywhere in the Dockerfile

### Gaps
- No HEALTHCHECK directive — LB/orchestrator cannot verify container readiness
- Runtime stage is unnamed (`AS runtime` missing) — minor; check calls for named stages
- Final image size (<200 MB) not verified but plausible (slim base + 3 pure-Python deps)

### Remediation
```diff
- FROM python:3.11
- WORKDIR /app
- COPY . .
- RUN pip install -e .
- CMD ["python", "-m", "server"]
+ FROM python:3.11-slim AS builder
+ WORKDIR /build
+ COPY pyproject.toml .
+ COPY src/ ./src/
+ RUN pip install --no-cache-dir --user -e .
+
+ FROM python:3.11-slim AS runtime
+ COPY --from=builder /root/.local /root/.local
+ COPY src/ /app/src/
+ WORKDIR /app
+ ENV PATH=/root/.local/bin:$PATH PYTHONUNBUFFERED=1
+ USER nobody
+ HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
+ CMD ["python", "-m", "server"]
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-006
**PDF-Reference:** Sec 5.3

### Observed Behavior
Check evaluated as **fail** against the current code.

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


### SDK-001

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


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **partial** against the current code.

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


### SDK-004

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


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- client.py:41-74 — all three dataset URLs are hardcoded module constants (https:// on data.finance.admin.ch / efv.admin.ch); no user input ever builds a URL, so the primary SSRF vector is structurally absent
- client.py:122-123 — httpx.AsyncClient uses default TLS verification (never disabled) but follow_redirects=True
- SECURITY.md:22 & README.md:180-182 — documents fixed hardcoded egress, 'no SSRF surface'

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
Check evaluated as **partial** against the current code.

### Evidence
- client.py:42,58,64,70 — hostnames are fixed trusted EFV constants, not user-controlled, so an attacker cannot introduce a rebinding domain
- client.py:122-123 — httpx default client, no custom transport, no DNS pinning; follow_redirects=True

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
Check evaluated as **partial** against the current code.

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


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- server.py:191-248 — FastMCP derives an input schema from the typed signatures, so type-level validation exists (e.g. year_from: int | None is enforced as int; a non-int LLM value is rejected at the boundary)
- server.py:191-233 — tool args (variable: str, household: str, level: int, contains: str|None) only filter already-cached in-memory rows; they never build a URL, reach a subprocess, or hit SQL (harmless sink)
- models.py:19-88 — Pydantic v2 envelopes exist but are response models, not input-constraint schemas

### Gaps
- No numeric ge/le constraints on int args (level, year_from, year_to) — LLM can pass arbitrary/negative/huge ints
- No str min_length/max_length or whitelist pattern on string args (variable, household, model, topic, contains, departement)
- No Pydantic strict=True and no extra='forbid' on any input model
- SECURITY.md:25 overstates this as full 'Pydantic v2 validation at all tool boundaries' — only type validation is present, not constraint validation

### Remediation
### Schritt 1: Schema pro Tool extrahieren

```diff
+ from typing import Annotated
+ from pydantic import BaseModel, Field, StringConstraints
+
+ class SearchArgs(BaseModel):
+     model_config = {"strict": True, "extra": "forbid"}
+     query: Annotated[str, StringConstraints(min_length=2, max_length=200)]
+     limit: Annotated[int, Field(ge=1, le=100)] = 10

  @mcp.tool()
- async def search(query: str, limit: int = 10) -> dict:
+ async def search(args: SearchArgs, ctx: Context) -> dict:
-     return await db.search(query, limit=limit)
+     return await db.search(args.query, limit=args.limit)
```

### Schritt 2: ValidationError sauber behandeln

```python
from pydantic import ValidationError

@mcp.tool()
async def search(args: SearchArgs, ctx: Context) -> dict:
    try:
        # Pydantic validiert beim Parsing automatisch — kein Aufruf nötig
        # Falls manuell aus dict gebaut: SearchArgs.model_validate(raw_dict)
        return await db.search(args.query, limit=args.limit)
    except ValidationError as e:
        # Wird normal nicht erreicht (FastMCP fängt das ab),
        # aber Defense-in-Depth:
        return {
            "isError": True,
            "content": [TextContent(
                type="text",
                text=f"Invalid arguments: {e.errors()[0]['msg']}"
            )],
        }
```

### Schritt 3: Tests gegen Edge-Cases

```python
@pytest.mark.parametrize("invalid_args,expected_error", [
    ({"query": "a", "limit": 10}, "min_length"),       # zu kurz
    ({"query": "x"*500, "limit": 10}, "max_length"),   # zu lang
    ({"query": "test", "limit": 0}, "greater_than_or_equal"),
    ({"query": "test", "limit": 99999}, "less_than_or_equal"),
    ({"query": "test", "limit": 10, "evil": "field"}, "extra_forbidden"),
])
async def test_search_rejects_invalid(invalid_args, expected_error):
    with pytest.raises(ValidationError) as exc:
        SearchArgs.model_validate(invalid_args)
    assert any(expected_error in err["type"] for err in exc.value.errors())
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- client.py:41-74 — egress is de-facto fixed to three hardcoded https constants on two EFV hosts; no user input can introduce a new host (stronger than a mutable allow-list in that dimension)
- README.md:180-182 & SECURITY.md:22 — the two allowed EFV hosts and fixed-egress posture are documented
- client.py:122-123 — single httpx client; TLS verification on

### Gaps
- No explicit code-layer allow-list: no frozenset ALLOWED_HOSTS and no assert_host_allowed() pre-request guard (grep finds neither)
- No network-layer egress control (no k8s NetworkPolicy, no docs/network-egress.md, no security-group rules)
- follow_redirects=True (client.py:123) permits a redirect to leave the fixed EFV hosts with no host re-check
- No documented update procedure for changing the egress set

### Remediation
### Schritt 1: Allow-List-Inventar

Pro Server alle ausgehenden HTTP-Hosts identifizieren:

```bash
grep -rE 'https://[a-z0-9.-]+' src/ | \
  sed -E 's/.*https:\/\/([a-z0-9.-]+).*/\1/' | sort -u
```

Resultat: minimale Allow-Liste.

### Schritt 2: Code-Layer einbauen

Wie Pass-Pattern Modus 1.

### Schritt 3: Network-Layer einbauen

Bei Kubernetes: NetworkPolicy wie oben. Bei AWS: Security Group mit egress-Rules. Bei Cloudflare WARP: Zero-Trust-Policy.

### Schritt 4: Tests gegen Regression

```python
async def test_egress_blocked_to_non_allowlisted_host():
    with pytest.raises(PermissionError, match="not in allow-list"):
        await fetch_external_data("https://evil.example.com/", mock_ctx())


async def test_egress_allowed_to_allowlisted_host():
    # Mock-Response, kein echter Network-Call
    with respx.mock:
        respx.get("https://opendata.swiss/api/...").respond(200, json={"ok": True})
        result = await fetch_external_data("https://opendata.swiss/api/...", mock_ctx())
        assert result["ok"]
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
Check evaluated as **partial** against the current code.

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
2. **ARCH-009** (high, fail)
3. **OBS-001** (high, fail)
4. **OBS-002** (high, partial)
5. **OPS-001** (high, partial)
6. **OPS-003** (high, partial)
7. **SCALE-002** (high, fail)
8. **SCALE-003** (high, fail)
9. **SDK-001** (high, fail)
10. **SDK-004** (high, fail)
11. **SEC-005** (high, partial)
12. **SEC-007** (high, partial)
13. **SEC-018** (high, partial)
14. **SEC-021** (high, partial)
15. **SEC-022** (high, partial)
16. **ARCH-002** (medium, partial)
17. **ARCH-003** (medium, partial)
18. **ARCH-012** (medium, partial)
19. **OBS-003** (medium, fail)
20. **OBS-006** (medium, fail)
21. **SCALE-004** (medium, partial)
22. **SCALE-006** (medium, fail)
23. **SDK-002** (medium, partial)
24. **SDK-003** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-07-25` |


_Generated by tools/build_report.py — do not edit by hand._
