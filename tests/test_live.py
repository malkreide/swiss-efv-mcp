"""Live tests against the real EFV endpoints.

Run explicitly:  PYTHONPATH=src pytest -m live
Excluded from CI: pytest -m "not live"
"""

import pytest

from swiss_efv_mcp.client import EFVClient
from swiss_efv_mcp.server import budget_impl, dimensions_impl, headline_impl

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
