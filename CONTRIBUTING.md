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

## The live suite: when it runs, and who sees a red result

**Cadence:** daily at 05:27 UTC, plus on demand via *Actions → Live tests → Run
workflow*. See [`.github/workflows/live.yml`](.github/workflows/live.yml).

**Who sees it:** A red run opens an issue labelled `upstream` and the stable title “Live-Tests gegen data.finance.admin.ch rot (<Datum>)”. A second red run recognises the open issue by its title prefix and appends to that same thread rather than opening a second one. Once the suite is green again, the issue closes itself.

**Three answers, not two.** `scripts/classify_live_run.py` reads the JUnit XML rather than
the exit code and separates `clear` (ran, green), `finding` (ran, something
fell) and `unknown` (did not run — install failed, nothing collected,
everything skipped). An `unknown` never closes an issue: closing would claim a
comparison that never happened.

**A red live run does not necessarily mean *our* bug.** It means the contract
with the source has changed, or the source is down. Both belong seen; only the
first belongs fixed. Please read the run before disabling the job — that is how
this check dies, and it is the only one in the repository that can contradict a
wrong assumption about data.finance.admin.ch. Every other test asserts against a fixture, and
the fixture was written from the same assumption as the code.
