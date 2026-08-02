# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Behoben

- **Fehlermeldung bei unerreichbarem Upstream nannte den Fehler nicht.**
  `RuntimeError: Upstream unreachable after retries: ` endete im Nichts, weil
  `httpx.ConnectTimeout` / `ReadTimeout` / `ConnectError` ein leeres `str()`
  tragen. Die Meldung nennt jetzt immer den Exception-Typ und den Host, also
  z. B. `Upstream unreachable after 4 attempts: ConnectTimeout: no further
  detail (host=www.data.finance.admin.ch)`, und verkettet die Ursache via
  `raise ... from`. Damit ist eine voruebergehende Netzstoerung auf einen Blick
  von einer kaputten URL zu unterscheiden. Der Wortlaut bleibt intern — nach
  aussen maskiert `mask_error_details` weiterhin auf den Typnamen (OBS-002).

### Geaendert

- **Die Live-Suite teilt sich einen `EFVClient`.** Bisher legte jeder Test eine
  eigene Instanz an, womit der Cache nutzlos war und derselbe Dump mehrfach
  geladen wurde. Beim Ausfall am 2026-08-01 lief deshalb viermal dieselbe
  aussichtslose Retry-Leiter: vier Tests, 17 Minuten. Jetzt wird jeder Datensatz
  einmal pro Lauf geholt (Suite-Laufzeit ~10 s), der geteilte Connection-Pool
  wird beim Teardown geschlossen statt pro Test zu lecken, und die Suite nutzt
  engere Timeouts (30 s statt 60 s, Backoff 1.0 statt 2.0): ein toter Upstream
  meldet sich in etwa einer Minute. Der `live`-Workflow bekommt zusaetzlich
  `timeout-minutes: 10` als Backstop.

## [0.3.1] - 2026-07-31

### Geaendert

- **Der Server gibt sich nicht mehr als Chrome aus.** Bis 0.3.0 sendete er
  `Mozilla/5.0 (X11; Linux x86_64) ... Chrome/124.0 Safari/537.36`, mit dem
  Vermerk, die Endpunkte wiesen alles andere mit 403 ab (gemessen 2026-07-24).

  Am 2026-07-31 nachgemessen: alle drei Datensatz-URLs auf beiden Hosts, je
  vier User-Agents — Chrome, die ehrliche Kennung, `curl/8.5.0` und ganz ohne
  UA-Header. Jede Anfrage antwortete 200/206; die ehrliche Kennung anschliessend
  dreimal ueber alle drei Datensaetze wiederholt, neun von neun erfolgreich.
  Die Einschraenkung besteht nicht mehr.

  Neu sendet der Server `swiss-efv-mcp/<version> (+github.com/...)` aus den
  Paket-Metadaten. Eine gefaelschte Kennung kostet den Betreiber die
  Moeglichkeit, uns in seinen Logs zu erkennen und uns bei Fehlverhalten zu
  erreichen — das ist nur fuer eine Sperre zu zahlen, die es tatsaechlich gibt.
  Sollte die EFV wieder filtern, gehoert zum Zurueckdrehen die Aktualisierung
  des Vermerks: eine veraltete Begruendung ist der Grund, warum diese hier so
  lange unhinterfragt blieb.

## [0.3.0] - 2026-07-25

Medium-findings audit backlog worked through — 0 failing checks; the three
remaining findings are accepted-risk ADR-documented deferrals (SCALE-002,
SCALE-003, SEC-005). See the audit runs under `audits/`.

### Added
- **ARCH-012:** the MCP protocol baseline (`2025-11-25`) is pinned as
  `MCP_PROTOCOL_VERSION` in `server.py`, with a regression test that fails CI if
  a SDK bump changes the negotiated version.
- **SEC-022:** `dump_status` renamed to `fiscal_status` so every tool shares the
  `fiscal_` server-identity namespace; `dump_status` is kept as a documented
  deprecated alias (removed in a future minor). Tool-hash pinning is documented
  as a gateway responsibility in `SECURITY.md`.
- **SCALE-003:** ADR 0002 gains a concrete `Mcp-Session-Id` sticky-session
  example (nginx / Ingress / Traefik) for the multi-replica case.
- **SEC-005:** `docs/network-egress.md` prescribes the network-layer egress
  mitigation (default-deny NetworkPolicy / egress-proxy allow-list) that
  supersedes application-level DNS pinning.
- **SDK-002:** tools now return typed Pydantic models, so FastMCP exposes an
  output schema and structured content for every tool.
- **SDK-003:** `Context` injection — tools emit debug logs and `fiscal_list_dimensions`
  reports progress while loading the dumps.
- **ARCH-002:** tool descriptions carry explicit use-case context.
- **ARCH-003:** empty results return a guidance `note` (pointing at
  `fiscal_list_dimensions` or a different level) instead of a silent empty.
- **OBS-006:** optional OpenTelemetry tracing via the `otel` extra, gated by
  `EFV_MCP_OTEL_ENABLED` (off by default; `src/swiss_efv_mcp/_otel.py`).
- **SCALE-006 / SEC-007:** `compose.yaml` with CPU/memory limits, read-only root
  filesystem, dropped capabilities and `no-new-privileges`.
- **OPS-001:** per-tool live tests (`fiscal_by_institution`, `dump_status`) and a
  scheduled/manual live-test workflow (`.github/workflows/live.yml`).
- **OPS-003:** `docs/roadmap.md` documenting the phase architecture and the
  audit backlog.

### Security
- **SEC-004:** the egress guard now rejects IP-literal hosts and re-asserts the
  allow-list on the final URL after redirects.

## [0.2.0] - 2026-07-25

First public release. Portfolio alignment plus the security/observability
hardening from the MCP best-practice audit (production-ready; audit artifacts
under `audits/`).

### Security
- **SEC-021 — egress allow-list:** an immutable `ALLOWED_HOSTS` frozenset +
  `assert_host_allowed()` (HTTPS-only, two fixed EFV hosts) is enforced before
  every request in `client.py`; documented in `docs/network-egress.md`.
- **OBS-002 — error-detail masking:** raw upstream/internal exception text is no
  longer surfaced to the model; tool results carry a generic message and
  `mask_error_details=True`, with full detail logged to stderr.
- **SEC-018 — input bounds:** tool arguments carry explicit Pydantic constraints
  (year `1900–2100`, `level 1–8`, string `max_length`).
- **SDK-004 — default-deny CORS:** the SSE/HTTP transport sets explicit
  `allowed_origins` (via `EFV_MCP_CORS_ORIGINS`) and exposes only `Mcp-Session-Id`.
- **SEC-005 / SCALE-002 / SCALE-003 — accepted-risk ADRs:** DNS pinning
  (`docs/adr/0001`) and stateful load balancing (`docs/adr/0002`) are deliberately
  deferred with documented re-evaluation triggers.

### Added
- **MCP best-practice audit** against the portfolio catalogue (68 checks, 44
  applicable) under `audits/`: a baseline run and a post-remediation re-audit —
  **production-ready** (0 blocking findings; 17 → 26 pass). Reproducible from the
  stored `verification-results.json` / `summary.json`.
- Tool annotations `readOnlyHint: true` / `destructiveHint: false` on all five
  tools (ARCH-009).
- Structured logging via `structlog` (JSON to stderr) in `logging_config.py`
  (OBS-003 / OBS-004).
- Typed configuration via `pydantic-settings` (`settings.py`); new env vars
  `EFV_MCP_LOG_LEVEL`, `EFV_MCP_CORS_ORIGINS`, plus `EFV_MCP_`-prefixed aliases.
- Shared, lifespan-managed httpx client (one connection pool reused across dumps,
  closed on shutdown) (SDK-001).
- Hardened `Dockerfile`: named runtime stage + `HEALTHCHECK` (SCALE-004).
- Expanded test suite (`tests/test_hardening.py`): egress allow-list, error
  masking, tool annotations, settings, shared-client reuse, and the
  execution-error / protocol-error paths.

### Changed
- `__main__.py` rebuilt for FastMCP 3.x: network transports are served via
  `mcp.http_app(...)` + uvicorn with CORS, fixing the former `mcp.settings` path.
- Repository documentation and structure aligned with the Swiss Public Data MCP
  Portfolio convention.
- `SECURITY.md` / `SECURITY.de.md`: security posture, accepted-risk decisions, and
  the vulnerability-reporting process; linked from both READMEs.
- `CONTRIBUTING.md` / `CONTRIBUTING.de.md` and `PUBLISHING.md` (step-by-step PyPI
  release via Trusted Publishing).
- GitHub Actions CI workflow (`.github/workflows/ci.yml`): ruff + offline pytest
  on Python 3.11–3.13, with a CI status badge in both READMEs.
- `Publish to PyPI` workflow (`.github/workflows/publish.yml`) using PyPI Trusted
  Publishing (OIDC) on GitHub Release, plus MCP Registry publishing; `server.json`
  registry manifest.
- Dependabot config (`.github/dependabot.yml`): monthly `pip` and
  `github-actions` updates.
- Hardened non-root `Dockerfile` (SSE) and `.dockerignore`; `.gitignore`.
- README sections aligned with the portfolio: portfolio banner, linked badges,
  `Available Tools`, `Safety & Limits`, `Project Phase`, `MCP Protocol Version`,
  `Security` and `Contributing`, plus the `mcp-name` registry footer.

### Changed
- Distribution metadata in `pyproject.toml`: `LICENSE`-referenced license,
  per-version Python classifiers (3.11–3.13), author `Hayal Oezkan`, and
  `Repository` / `Issues` / `Changelog` / `Portfolio` project URLs.

### Security
- SSE transport now binds to `127.0.0.1` (loopback) by default instead of
  `0.0.0.0`. Binding to `0.0.0.0` is an explicit opt-in for containers (the
  provided `Dockerfile` sets it). README / SECURITY updated.

## [0.1.0] - 2026-07-24

### Added
- Initial release: MCP server for Swiss federal finances (EFV), Architecture C (Dump-first).
- Tools: `fiscal_headline`, `fiscal_budget_breakdown`, `fiscal_by_institution`,
  `fiscal_list_dimensions`, `dump_status`.
- Dual transport (stdio / SSE), retry with exponential backoff, 24 h TTL cache,
  Pydantic v2 envelopes with `source` + `provenance`.
- respx mock tests (Happy / Retry-on-503 / Timeout / Graceful degradation) plus
  `@pytest.mark.live` tests against the real endpoints.

### Known findings (from live probe 2026-07-24)
- **403 without UA**: `data.finance.admin.ch` and `efv.admin.ch` reject the default
  httpx/curl User-Agent; a browser UA is injected in `client.py`.
- **Landing-page trap**: opendata.swiss lists two datasets as "CSV" but the URL
  serves HTML; real files resolved to DAM paths (`/dam/de/sd-web/{id}/{name}_de.csv`)
  whose opaque id may rotate on re-upload.
- **NA-as-string**: `hh` / `model` / `source` use the literal "NA" for missing;
  centralised `clean()` maps null-ish tokens to `None`.
- **Projection is not one label**: the Bund labels future years "Budget/financial
  plans"; the aggregate state (`staat`) uses "Forecasts". `is_projection` abstracts
  over both so agents need not know the taxonomy.
- **Accounting-model seam 2022/2023**: budget topics split into "bis 2022" and
  "ab 2023"; a `note` flags affected breakdowns.
- **Detail cubes deferred**: `standardauswertung.csv` (157 MB) and `fir_art_funk.csv`
  (1.23 GB) are out of scope for v0.1.0 (Phase 2: pre-process to SQLite/Parquet).
