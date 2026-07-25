# Contributing

[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)

Thanks for your interest in `swiss-efv-mcp`. This is a read-only MCP server over
the public EFV dump files; contributions should keep it that way.

## Ground rules

- **Read-only.** Every tool stays read-only by design (HTTP GET only). No write,
  send, or filesystem capability.
- **Fixed egress.** Requests go only to the hardcoded EFV dataset URLs on
  `data.finance.admin.ch` and `efv.admin.ch`; tool arguments filter cached rows,
  they never build a URL.
- **No secrets.** The endpoints are unauthenticated public OGD; do not add
  credential handling.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

PYTHONPATH=src pytest tests/ -m "not live"   # offline, respx-mocked
PYTHONPATH=src pytest tests/ -m live         # hits the real EFV endpoints
ruff check src tests
```

## Pull requests

- Add tests for user-facing changes; keep `ruff check` and the offline suite green.
- Add a `CHANGELOG.md` entry under `[Unreleased]`.
- Update both `README.md` and `README.de.md` for any documentation change.
- For release/publishing, see [`PUBLISHING.md`](PUBLISHING.md).

## Reporting security issues

See [`SECURITY.md`](SECURITY.md) — please use private reporting, not public issues.
