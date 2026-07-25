<!-- Part of the Swiss Public Data MCP Portfolio · https://github.com/malkreide -->

# swiss-efv-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-model--context--protocol-black)

> MCP server for Swiss federal finances (EFV): budget, debt, forecasts and spending by task and institution.

[🇩🇪 Deutsche Version](README.de.md)

---

## Overview

This server closes the fiscal gap in the portfolio's Economics & Finance cluster.
`swiss-snb-mcp` already covers monetary policy; `swiss-efv-mcp` adds the **state
budget** — federal revenue, expenditure, balance, debt ratios (with forecasts to
2029), a hierarchical budget drill-down, and spending by department. Data comes
from the Eidgenössische Finanzverwaltung (EFV) via opendata.swiss (OGD Schweiz).

It is a **private, non-affiliated** project and carries no institutional mandate.

## 🎯 Anchor Demo Query

> *"How has the federal balance developed since the SNB rate turnaround in 2022 —
> and which task areas absorbed the growth in spending?"*

```
fiscal_headline(variable="saldo", household="bund", year_from=2021)
fiscal_budget_breakdown(topic="Ausgaben nach Aufgabengebiet", level=2)
```

Cross-read with `swiss-snb-mcp`, this connects the interest-rate cycle to the
federal deficit — something neither server can answer alone.

## Features

- **`fiscal_headline`** — revenue / expenditure / balance / debt ratios over
  1990–2029, per household (bund, ktn, gdn, staat, sv) and model (FS / GFS).
  Every point carries `is_projection` so actuals and plan/forecast years are
  unambiguous.
- **`fiscal_budget_breakdown`** — hierarchical federal budget by topic
  (Ausgaben nach Art / nach Aufgabengebiet, Einnahmen, Bilanz, …).
- **`fiscal_by_institution`** — spending per department / administrative unit
  since 2007 (Personalausgaben, Informatik, external services, FTE).
- **`fiscal_list_dimensions`** — discover valid parameter values.
- **`dump_status`** — cache freshness and upstream health (graceful degradation).

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) / `uvx` (recommended) or `pip`

## Installation

```bash
uvx swiss-efv-mcp            # zero-install run (once published to PyPI)
# or
pip install swiss-efv-mcp
```

## Usage / Quickstart

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

Cloud (SSE, e.g. Railway / Render):

```bash
TRANSPORT=sse PORT=8000 swiss-efv-mcp
```

## Configuration

| Env var     | Default   | Purpose                                   |
|-------------|-----------|-------------------------------------------|
| `TRANSPORT` | `stdio`   | `stdio` (Claude Desktop) or `sse` (cloud) |
| `HOST`      | `0.0.0.0` | bind host for SSE                         |
| `PORT`      | `8000`    | bind port for SSE                         |

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

## Project Structure

```
swiss-efv-mcp/
├── src/swiss_efv_mcp/
│   ├── client.py      # dump-first data layer: retry, UA, NA-cleaning, TTL cache
│   ├── models.py      # Pydantic v2 envelopes (source + provenance)
│   ├── server.py      # 5 FastMCP tools + testable *_impl functions
│   └── __main__.py    # dual stdio / sse transport
└── tests/             # respx mock tests + @pytest.mark.live
```

## Testing

```bash
PYTHONPATH=src pytest -m "not live"   # CI: fast, no network
PYTHONPATH=src pytest -m live         # hits the real EFV endpoints
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## Credits & Related Projects

- Data: **Eidgenössische Finanzverwaltung EFV** via opendata.swiss (OGD Schweiz, frei nutzbar)
- Companion: [`swiss-snb-mcp`](https://github.com/malkreide) (monetary policy) — the fiscal/monetary pair
- Part of the **Swiss Public Data MCP Portfolio**

## License

MIT License — see [LICENSE](LICENSE)

## Author

malkreide · [github.com/malkreide](https://github.com/malkreide)

> Disclaimer: private project, independent of any employer or institution. No warranty; figures are not authoritative — consult the EFV originals for official use.
