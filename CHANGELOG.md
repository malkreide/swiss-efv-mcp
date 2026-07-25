# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
