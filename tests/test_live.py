"""Live tests against the real EFV endpoints.

Run explicitly:  PYTHONPATH=src pytest -m live
Excluded from CI: pytest -m "not live"
"""

import pytest

from swiss_efv_mcp.client import EFVClient
from swiss_efv_mcp.server import (
    budget_impl,
    dimensions_impl,
    headline_impl,
    institution_impl,
    status_impl,
)

pytestmark = pytest.mark.live


async def test_live_headline_saldo_has_projection():
    # For the Bund, forward years are labelled "Budget/financial plans", not
    # "Forecasts" — is_projection abstracts over that.
    c = EFVClient()
    res = await headline_impl(c, variable="saldo", household="bund", model="fs")
    assert len(res.points) > 20
    assert any(p.is_projection for p in res.points)
    assert res.points[-1].year >= 2028  # plan horizon reaches out


async def test_live_staat_has_forecasts_label():
    # The aggregate state does use the "Forecasts" label.
    c = EFVClient()
    res = await headline_impl(c, variable="einnahmen", household="staat", model="fs")
    assert any(p.kind == "Forecasts" for p in res.points)


async def test_live_dimensions_nonempty():
    c = EFVClient()
    dims = await dimensions_impl(c)
    assert "einnahmen" in dims.headline_variables
    assert "Ausgaben nach Aufgabengebiet" in dims.budget_topics


async def test_live_budget_breakdown():
    c = EFVClient()
    res = await budget_impl(c, topic="Ausgaben nach Aufgabengebiet", level=2)
    assert len(res.items) >= 3


async def test_live_by_institution_personalausgaben():
    # OPS-001: the by-institution tool must be exercised against the real dump.
    c = EFVClient()
    res = await institution_impl(c, variable="Personalausgaben")
    assert len(res.points) > 0
    assert min(p.year for p in res.points) >= 2007  # coverage starts in 2007


async def test_live_dump_status_healthy_after_load():
    # OPS-001: dump_status must report a healthy, populated state after a load.
    c = EFVClient()
    await c.load("headline")
    report = status_impl(c)
    assert report.healthy is True
    assert report.datasets["headline"]["cached_rows"] > 0
