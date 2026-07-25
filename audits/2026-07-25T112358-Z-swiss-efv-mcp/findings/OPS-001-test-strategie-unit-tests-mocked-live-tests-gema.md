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
