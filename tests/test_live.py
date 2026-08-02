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

import pytest
import pytest_asyncio

from swiss_efv_mcp.client import EFVClient
from swiss_efv_mcp.server import (
    budget_impl,
    dimensions_impl,
    headline_impl,
    institution_impl,
    status_impl,
)

pytestmark = [pytest.mark.live, pytest.mark.asyncio(loop_scope="session")]

# The production defaults now carry the tight bound themselves — a 25s total
# budget over the whole call (ARCH-014), so the suite no longer needs to
# undercut the per-request timeout. Only the backoff is still shortened: the
# suite is a monitor, and a dead source should show up in seconds rather than
# in the production ladder's 2/4/8. The dumps are 0.5-5 MB and answer in
# seconds when the source is alive.
_LIVE_BACKOFF = 1.0  # 1s, 2s, 4s between the four attempts


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    c = EFVClient(backoff_base=_LIVE_BACKOFF)
    try:
        yield c
    finally:
        await c.aclose()


async def test_live_headline_saldo_has_projection(client):
    # For the Bund, forward years are labelled "Budget/financial plans", not
    # "Forecasts" — is_projection abstracts over that.
    res = await headline_impl(client, variable="saldo", household="bund", model="fs")
    assert len(res.points) > 20
    assert any(p.is_projection for p in res.points)
    assert res.points[-1].year >= 2028  # plan horizon reaches out


async def test_live_staat_has_forecasts_label(client):
    # The aggregate state does use the "Forecasts" label.
    res = await headline_impl(client, variable="einnahmen", household="staat", model="fs")
    assert any(p.kind == "Forecasts" for p in res.points)


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
