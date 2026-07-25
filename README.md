> 🇨🇭 Part of the [**Swiss Public Data MCP Portfolio**](https://github.com/malkreide/swiss-public-data-mcp) — open-source MCP servers connecting AI agents to Swiss public and open data.
> This is a private project. It is independent of any employer or institutional affiliation.

# 🏛️ swiss-efv-mcp

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)
[![CI](https://github.com/malkreide/swiss-efv-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-efv-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-8A2BE2.svg)](https://modelcontextprotocol.io/)
[![Auth: none](https://img.shields.io/badge/auth-none-brightgreen.svg)](#architecture-decision)
[![Portfolio](https://img.shields.io/badge/portfolio-swiss--public--data--mcp-informational)](https://github.com/malkreide/swiss-public-data-mcp)

> MCP server for Swiss federal finances (EFV): budget, debt, forecasts and spending by task and institution.

[🇩🇪 Deutsche Version](README.de.md)

## Overview

This server closes the fiscal gap in the portfolio's Economics & Finance cluster.
`swiss-snb-mcp` already covers monetary policy; `swiss-efv-mcp` adds the **state
budget** — federal revenue, expenditure, balance, debt ratios (with forecasts to
2029), a hierarchical budget drill-down, and spending by department. Data comes
from the Eidgenössische Finanzverwaltung (EFV) via opendata.swiss (OGD Schweiz).

## Features

- Five read-only tools over the curated EFV FS/GFS dump files.
- Headline series 1990–2029 per household (bund, ktn, gdn, staat, sv) and model
  (FS / GFS); every point carries `is_projection` so actuals and plan/forecast
  years are unambiguous.
- Hierarchical federal-budget drill-down and spending by department / unit.
- 24 h TTL in-memory cache with stale-serve fallback; retry with exponential
  backoff (2/4/8 s); `dump_status` never returns empty silently.
- Dual transport: `stdio` (local) and SSE (cloud).
- No authentication required — public open-government data (No-Auth-First).

## 🎯 Anchor Demo Query

> *"How has the federal balance developed since the SNB rate turnaround in 2022 —
> and which task areas absorbed the growth in spending?"*

```
fiscal_headline(variable="saldo", household="bund", year_from=2021)
fiscal_budget_breakdown(topic="Ausgaben nach Aufgabengebiet", level=2)
```

Cross-read with `swiss-snb-mcp`, this connects the interest-rate cycle to the
federal deficit — something neither server can answer alone.

## Prerequisites

- Python 3.11+
- [`uv` / `uvx`](https://docs.astral.sh/uv/) (recommended) or `pip`
- Network access to `data.finance.admin.ch` and `efv.admin.ch` — no API key needed

## Installation

```bash
uvx swiss-efv-mcp            # zero-install run (once published to PyPI)
# or
pip install swiss-efv-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "swiss-efv": {
      "command": "uvx",
      "args": ["swiss-efv-mcp"]
    }
  }
}
```

## Quickstart

```bash
# Run locally over stdio (default transport)
uvx swiss-efv-mcp

# From a checkout, without installing
PYTHONPATH=src python -m swiss_efv_mcp
```

## Configuration

All configuration is loaded once into a typed `Settings` object
(`pydantic-settings`). The legacy unprefixed names below keep working; the
canonical names use the `EFV_MCP_` prefix. Defaults are safe for local use.

| Variable    | Default     | Purpose                                                                    |
|-------------|-------------|----------------------------------------------------------------------------|
| `TRANSPORT` | `stdio`     | Transport: `stdio` (Claude Desktop) or `sse` / `streamable-http` (cloud)   |
| `HOST`      | `127.0.0.1` | Bind host (SSE only). Loopback by default; set `0.0.0.0` **only** in a container |
| `PORT`      | `8000`      | Bind port (SSE only)                                                        |
| `EFV_MCP_LOG_LEVEL`    | `INFO` | structlog level (JSON to stderr)                                  |
| `EFV_MCP_CORS_ORIGINS` | `[]`   | SSE only: explicit allowed browser origins (default-deny; comma-separated or JSON) |

Cloud (Render / Railway):

```bash
TRANSPORT=sse PORT=8000 swiss-efv-mcp   # exposes /sse
```

## Available Tools

| Tool | Purpose |
|---|---|
| `fiscal_headline` | Revenue / expenditure / balance / debt ratios over 1990–2029, per household and model; every point flags `is_projection` |
| `fiscal_budget_breakdown` | Hierarchical federal budget by topic (Ausgaben nach Art / nach Aufgabengebiet, Einnahmen, Bilanz, …) |
| `fiscal_by_institution` | Spending per department / administrative unit since 2007 (Personalausgaben, Informatik, external services, FTE) |
| `fiscal_list_dimensions` | Discover valid parameter values — call this first to build correct arguments |
| `dump_status` | Cache freshness and upstream health per dataset; never returns empty silently |

All tools are **read-only**: each is annotated `readOnlyHint: true`,
`destructiveHint: false`, only issues HTTP GETs against the EFV dump files, and
has no write, send, or filesystem capability.

**MCP primitives.** This server uses only the **Tools** primitive. The EFV data
are sliced live from cached dumps with no stable resource hierarchy to expose as
*Resources*, and there are no server-authored *Prompts*. The five tools are small
and closely related, so they live in a single `server.py` rather than a `tools/`
package.

## Architecture

```
                      ┌──────────────────────────────┐
   Claude / Agent ──▶ │  swiss-efv-mcp (FastMCP)      │
                      │  5 tools · Pydantic v2 env.   │
                      └───────────────┬──────────────┘
                                      │ fetch + retry + TTL cache
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
   data.finance.admin.ch                          efv.admin.ch/dam
   fs_dashboard/main_extern.csv                   bundeshaushalt_de.csv
   (headline, 1990–2029)                          institutionen_de.csv
```

## Architecture decision

This server uses **Architecture C (Dump-first)**.

Rationale (verified live on 2026-07-24):
- The EFV FS/GFS dashboard has **no filtered query API**; it serves static CSV
  dumps that its front-end filters in the browser.
- Three curated files are small enough to fetch-and-cache whole (516 KB / 5 MB /
  1 MB). They cover the headline aggregates, the hierarchical budget and the
  by-institution view — i.e. the answerable questions.
- The full detail cubes (`standardauswertung.csv` 157 MB, `fir_art_funk.csv`
  1.23 GB) are **out of scope for v0.1.0**; loading them per request is not
  viable. A future Phase 2 would pre-process them into SQLite/Parquet.

Consequences:
- Files are cached in memory with a 24 h TTL; stale cache is preferred over an
  empty response when upstream is down.
- Retry with exponential backoff on all HTTP; `dump_status` always returns a
  readable state.

## Project Structure

```
swiss-efv-mcp/
├── src/swiss_efv_mcp/
│   ├── __init__.py
│   ├── __main__.py        # entry point; dual transport (stdio / SSE+CORS)
│   ├── client.py          # dump-first data layer: egress allow-list, retry, UA, TTL cache
│   ├── logging_config.py  # structlog JSON to stderr
│   ├── models.py          # Pydantic v2 envelopes (source + provenance)
│   ├── server.py          # 5 FastMCP tools (annotated) + testable *_impl functions
│   └── settings.py        # typed pydantic-settings config
├── tests/                 # respx mock tests + hardening tests + @pytest.mark.live
├── docs/                  # network-egress.md + accepted-risk ADRs
├── audits/                # MCP best-practice audit runs (findings, report, summary)
├── README.md · README.de.md · CHANGELOG.md · SECURITY.md · CONTRIBUTING.md
├── Dockerfile · server.json · LICENSE
└── pyproject.toml
```

## Safety & Limits

- **Read-only.** Every tool is annotated `readOnlyHint: true`, only issues HTTP
  GETs against the EFV dump files, and has no write, send, or filesystem capability.
- **Egress allow-list.** An immutable `ALLOWED_HOSTS` frozenset + `assert_host_allowed()`
  is enforced before every request (HTTPS-only, two fixed EFV hosts). URLs are
  hardcoded constants; no user input builds a URL. See [`docs/network-egress.md`](docs/network-egress.md).
- **TLS on.** httpx certificate verification is on by default and never disabled.
- **No credentials.** The endpoints are public OGD; no API keys or secrets are
  stored or forwarded. A browser `User-Agent` is injected because the endpoints
  `403` the default httpx/curl UA (see Known limitations) — do not remove it.
- **Error masking.** `mask_error_details=True` plus client-side masking keep raw
  upstream/internal detail out of tool results; full detail goes only to the
  structlog stderr log.
- **Input bounds.** Tool arguments carry explicit Pydantic constraints (year
  `1900–2100`, `level 1–8`, string `max_length`).
- **Graceful degradation.** Retry with exponential backoff (2/4/8 s); a stale
  cache is served over an empty response; `dump_status` always returns a readable
  state and never a silent empty.
- **Loopback + default-deny CORS.** SSE binds to `HOST`, default `127.0.0.1`; set
  `HOST=0.0.0.0` **only** inside a container (the provided [`Dockerfile`](Dockerfile) does).
  Browser origins must be listed explicitly via `EFV_MCP_CORS_ORIGINS`.
- **Audited.** Reviewed against the portfolio MCP best-practice catalogue
  (44 applicable checks) — see [`audits/`](audits/) and [`SECURITY.md`](SECURITY.md).
  Accepted risks are documented as ADRs under [`docs/adr/`](docs/adr/).
- **Not authoritative.** Figures are not official; consult the EFV originals for
  official use.

## Known limitations

Live-probe findings (2026-07-24), also in `CHANGELOG.md → Known findings`:

| Finding | Impact |
|---|---|
| Endpoints return **HTTP 403 without a browser User-Agent** | UA is injected by the client; do not remove it |
| opendata.swiss "CSV" links for 2 datasets point to an **HTML landing page** | real files resolved to a DAM path (`/dam/de/sd-web/{id}/…`) whose opaque id may rotate on re-upload |
| `NA` appears as a literal string in `hh`/`model`/`source` | cleaned to `None` centrally |
| "Forward-looking" is **not one label**: Bund uses "Budget/financial plans", `staat` uses "Forecasts" | abstracted via `is_projection` |
| **Accounting-model break at 2022/2023** ("bis 2022" vs "ab 2023" topics) | series has a seam; a `note` flags affected topics |
| Detail cubes (157 MB / 1.23 GB) not served | Phase 2; use the curated files for now |

## Project Phase

This server is in **Phase 1 (read-only)**. Every tool only ever fetches the
public EFV dump files — there are no write, send, or filesystem capabilities.

| Phase | Scope | Status |
|---|---|---|
| **1 — Read-only** | Headline series, budget breakdown, spending by institution | ✅ current |
| 2 — Detail cubes | Pre-process the 157 MB / 1.23 GB cubes to SQLite/Parquet | planned |
| 3 — Multi-agent | (none planned) | — |

A transition to a later phase would require a re-audit before any write-capable
tool is added.

## MCP Protocol Version

The protocol version is negotiated at the `initialize` handshake by
[FastMCP](https://pypi.org/project/fastmcp/) (pinned `fastmcp>=3.4` in
`pyproject.toml`), which builds on the `mcp` Python SDK. Dependencies are kept
current via monthly Dependabot PRs (`.github/dependabot.yml`); protocol-relevant
bumps are noted in [`CHANGELOG.md`](CHANGELOG.md).

## Testing

```bash
PYTHONPATH=src pytest tests/ -m "not live"   # offline, respx-mocked
PYTHONPATH=src pytest tests/ -m live         # hits the real EFV endpoints
PYTHONPATH=src ruff check src tests
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Security

See [SECURITY.md](SECURITY.md) for the security posture, hardening controls, and
how to report a vulnerability.

## Contributing

Issues and pull requests are welcome. Please keep tools read-only, run
`ruff check` and the offline test suite before submitting, and add a
`CHANGELOG.md` entry under `[Unreleased]` for user-facing changes. See
[CONTRIBUTING.md](CONTRIBUTING.md).

Maintainers: see [PUBLISHING.md](PUBLISHING.md) for the step-by-step PyPI release
process (Trusted Publishing via GitHub Release).

## License

MIT for this server — see [LICENSE](LICENSE). The EFV data remain subject to the
OGD Schweiz terms (freely usable, with attribution).

## Author

**Hayal Oezkan** · [github.com/malkreide](https://github.com/malkreide)

## Credits & Related Projects

- Data: **Eidgenössische Finanzverwaltung EFV** via opendata.swiss (OGD Schweiz, freely usable)
- Companion: [`swiss-snb-mcp`](https://github.com/malkreide) (monetary policy) — the fiscal/monetary pair
- Portfolio index: [swiss-public-data-mcp](https://github.com/malkreide/swiss-public-data-mcp)

> Disclaimer: private project, independent of any employer or institution. No warranty; figures are not authoritative — consult the EFV originals for official use.

<!-- mcp-name: io.github.malkreide/swiss-efv-mcp -->
