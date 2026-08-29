"""Live tests against the real EFV endpoints.

Run explicitly:  PYTHONPATH=src pytest -m live
Excluded from CI: pytest -m "not live"

All tests share one session-scoped :class:`EFVClient`. That is deliberate: the
client caches per dataset, so each dump is fetched exactly once for the whole
suite instead of once per test. Before that, a run in which the headline host
was unreachable spent ~4 minutes per test re-running the same doomed retry
ladder (2026-08-01: four tests, 17 minutes, one transient outage). Sharing the
client also means the shared httpx connection pool is closed on teardown rather
than leaked per test.

The session-scoped client requires a session-scoped event loop, hence the
``loop_scope`` on both the fixture and the module-wide asyncio marker.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio

from swiss_efv_mcp.client import (
    _ACTUAL_SOURCES,
    _PROJECTION_SOURCES,
    EFVClient,
    clean,
    is_projection,
    to_year,
)
from swiss_efv_mcp.server import (
    budget_impl,
    dimensions_impl,
    headline_impl,
    institution_impl,
    status_impl,
)

pytestmark = [pytest.mark.live, pytest.mark.asyncio(loop_scope="session")]

# --- The client the suite runs on -------------------------------------------
#
# The production budget (ARCH-014) is anchored to what an MCP caller will still
# wait for: 25s over the whole call, per-request timeout 25s too. Those two
# being equal is what makes a hanging connect fatal on the first try — the
# per-request timeout and the budget deadline fall on the same instant, the
# budget wins, and `_fetch_with_retry` breaks out instead of retrying. Measured
# on 2026-08-18: `Upstream unreachable after 1 attempt(s), 25s budget spent`,
# four tests down, and the source answering 200 in 2.6s right after. Three of
# the four attempts this suite pays a backoff for never went out.
#
# For a nightly monitor the anchor is the wrong one. Nobody is waiting on a
# cron job, so the budget should not be sized by an MCP caller's patience. It
# is sized here so that ALL `_ATTEMPTS` attempts fit, including the backoff
# ladder at its widest jitter:
#
#     4 x 15s attempts + (1.5 + 3 + 6)s backoff = 70.5s   ->  75s budget
#
# The per-attempt timeout drops from 25s to 15s, and that is safe only because
# the retries now exist: before, a single slow answer was fatal. 15s is still
# more than twice the slowest dump measured against the live source (5 MB in
# 6.5s).
#
# THE COST, STATED
# ----------------
# A failed fetch is not cached, so every test that needs a dead dataset runs
# the full ladder again — that is the 2026-08-01 incident in the docstring
# above (four tests, 17 minutes). This budget re-opens a bounded share of it:
# seven tests at 75s is 8.75 minutes worst case, against the job's
# `timeout-minutes: 20`. `test_live_budget_fits_the_job_timeout` holds that
# pair together, with a safety factor of 2 — which is why adding the seventh
# test on 2026-08-29 required raising the job timeout from 15 minutes rather
# than merely noticing afterwards that it had grown too tight.
#
# The bound only bites on a TOTAL outage — and a total outage is what
# `live_streak.py` is there to name. A brief hiccup, the case this is for,
# costs only the attempts it actually takes: a source back on the second try
# costs ~16s, not 75.
_LIVE_BACKOFF = 1.0  # 1s, 2s, 4s between the four attempts
_LIVE_TIMEOUT = 15.0  # per attempt; production uses 25s
_LIVE_TOTAL_BUDGET = 75.0  # whole call; production uses 25s


def live_client() -> EFVClient:
    """The client this suite runs on.

    A function rather than three constants read from elsewhere: a test that
    asserts against the real object cannot pass while the fixture quietly uses
    different numbers.
    """
    return EFVClient(
        backoff_base=_LIVE_BACKOFF,
        timeout=_LIVE_TIMEOUT,
        total_budget=_LIVE_TOTAL_BUDGET,
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    c = live_client()
    try:
        yield c
    finally:
        await c.aclose()


async def test_live_source_vocabulary_is_fully_mapped(client):
    """Every `source` label in the dump must be one `is_projection` classifies.

    This is the test the 2026-08-27 drift needed and did not have. That night
    the EFV switched the whole column from English to German; `is_projection`
    fell through to `None` for all 6110 rows and `fiscal_headline` stopped
    flagging projections in production. The only symptom was two *other* tests
    failing with a bare `assert False`, and neither of them mentioned labels.

    An unmapped label is not a missing value. `None` from `is_projection` reads
    as "this row does not say", when what happened is that the taxonomy moved
    underneath us — so it has to be reported by name, not inferred from a
    downstream assertion that happens to sit on top of it.

    Asserted through `is_projection` itself rather than against a copy of the
    two sets: a copy would agree with itself while production went unmapped.
    """
    rows, _ = await client.load("headline")
    labels = {clean(r.get("source")) for r in rows}
    # `NA` is the source's own "missing", cleaned to None by `_NULLISH`. Those
    # rows genuinely carry no label; they are not a vocabulary we failed to map.
    labels.discard(None)
    assert labels, "the dump carries no `source` labels at all — column renamed?"
    unmapped = sorted(label for label in labels if is_projection(label) is None)
    assert not unmapped, (
        f"`source` labels the client cannot classify: {unmapped}. "
        f"Known: {sorted(_PROJECTION_SOURCES | _ACTUAL_SOURCES)}. "
        "The EFV changed its vocabulary — decide per label whether it is "
        "forward-looking or settled, then extend _PROJECTION_SOURCES / "
        "_ACTUAL_SOURCES in client.py. Do not guess a translation."
    )


async def test_live_headline_saldo_is_classified_and_current(client):
    """The Bund's balance series: long, fully classified, and still moving.

    Up to 2026-08-27 this test also asserted `any(p.is_projection)` and a plan
    horizon of `>= 2028`, because the dump carried the Bund's
    Voranschlag/Finanzplan years. That republish dropped them: `hh=bund` now
    ends at 2025 and every one of its rows is `Rechnung`. Those two assertions
    were claims about what the EFV chooses to publish, not about this server,
    and the source is entitled to change its mind — so the projection claim
    moved to `test_live_projections_survive_into_the_tool`, which asks the dump
    where forward years actually live instead of naming a household, and the
    horizon claim became the staleness floor below.
    """
    res = await headline_impl(client, variable="saldo", household="bund", model="fs")
    assert len(res.points) > 20
    # Every point classified. Without this, the language switch would have left
    # this test green: `is_projection=None` on all 36 points breaks nothing a
    # count of points can see.
    unclassified = [p.year for p in res.points if p.is_projection is None]
    assert not unclassified, f"years with an unclassifiable `source`: {unclassified}"
    # A staleness floor, not a horizon. `year - 1` would break every January,
    # when the previous year's Rechnung is not published yet; `year - 2` still
    # catches the case this is for — a dump nobody maintains any more.
    floor = datetime.now(UTC).year - 2
    assert res.points[-1].year >= floor, (
        f"series stops at {res.points[-1].year}, expected {floor} or later — the dump looks frozen"
    )


async def test_live_projections_survive_into_the_tool(client):
    """The dump still marks forward-looking years, and the flag reaches the tool.

    Asserted through `is_projection`, not against the label. Until 2026-08-27
    this read `p.kind == "Forecasts"` on `staat`/`einnahmen`; the source now
    writes `Prognosen` for the same thing, and pinning the next literal would
    just re-arm the same trap. What the server promises its callers is the
    flag, so that is what the live suite checks — the label vocabulary has its
    own test above.

    The household and variable are DERIVED from the dump, not written into the
    test. Pinning them re-armed a second trap: on 2026-08-29 `staat`/`fs`/
    `einnahmen` carried exactly ONE projection row (2025, `Prognosen`), out of
    75 in the whole file. The next vintage that settles the 2025 state accounts
    flips that single row to `Rechnung` and turns this red — for a change in
    what the EFV publishes, which is the very thing that made the old Bund test
    a bad test. Asking the file which slice to query keeps the claim on the
    server: wherever the source marks a projection, the tool must surface it.
    """
    rows, _ = await client.load("headline")
    vorausschauend = [r for r in rows if is_projection(clean(r.get("source"))) is True]
    assert vorausschauend, (
        "the dump carries no forward-looking rows at all. Either the EFV stopped "
        "publishing them, or their label is unmapped — "
        "`test_live_source_vocabulary_is_fully_mapped` tells the two apart."
    )

    # One raw row the file says is a projection, followed through the real tool.
    # A flag that exists in the CSV but is lost on the way out is exactly the
    # production failure this suite is for.
    #
    # THE POINT IS MATCHED BY YEAR, not merely looked for in the series.
    # `any(p.is_projection ...)` over the whole slice was the first version and
    # was wrong twice over: a slice with several projection years stays green
    # when THIS row is dropped or loses its flag, because another one satisfies
    # it — and the failure message names this row's year while asserting
    # nothing about it, so it would have reported a survival it never checked.
    #
    # On 2026-08-29 every slice happened to carry exactly one projection year
    # (75 rows, 75 slices), so the hole was latent rather than open. It is not
    # hypothetical: until 2026-08-27 the Bund's Voranschlag/Finanzplan ran
    # 2026-2029, four projection years to a slice, and a restored plan horizon
    # opens it again.
    zeile = vorausschauend[0]
    jahr = to_year(zeile["jahr"])
    res = await headline_impl(
        client,
        variable=clean(zeile["variable"]),
        household=clean(zeile["hh"]),
        model=clean(zeile["model"]),
    )
    herkunft = f"{zeile['hh']}/{zeile['model']}/{zeile['variable']}/{zeile['jahr']}"
    punkt = next((p for p in res.points if p.year == jahr), None)
    assert punkt is not None, (
        f"raw row {herkunft} is in the dump, but the tool returns no point for "
        f"that year — years it does return: {[p.year for p in res.points]}"
    )
    assert punkt.is_projection is True, (
        f"raw row {herkunft} is labelled {zeile['source']!r}, which "
        f"`is_projection` maps to True, but the point comes out with "
        f"is_projection={punkt.is_projection!r}"
    )
    # The raw label reaches the caller unchanged. `kind` is documented as
    # passed through verbatim, and that is the half `is_projection` cannot show.
    assert punkt.kind == clean(zeile["source"]), (
        f"raw row {herkunft} is labelled {zeile['source']!r}, but the point "
        f"carries kind={punkt.kind!r}"
    )


async def test_live_dimensions_nonempty(client):
    dims = await dimensions_impl(client)
    assert "einnahmen" in dims.headline_variables
    assert "Ausgaben nach Aufgabengebiet" in dims.budget_topics


async def test_live_budget_breakdown(client):
    res = await budget_impl(client, topic="Ausgaben nach Aufgabengebiet", level=2)
    assert len(res.items) >= 3


async def test_live_by_institution_personalausgaben(client):
    # OPS-001: the by-institution tool must be exercised against the real dump.
    res = await institution_impl(client, variable="Personalausgaben")
    assert len(res.points) > 0
    assert min(p.year for p in res.points) >= 2007  # coverage starts in 2007


async def test_live_dump_status_healthy_after_load(client):
    # OPS-001: dump_status must report a healthy, populated state after a load.
    await client.load("headline")
    report = status_impl(client)
    assert report.healthy is True
    assert report.datasets["headline"]["cached_rows"] > 0
