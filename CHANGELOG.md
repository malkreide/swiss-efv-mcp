# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
