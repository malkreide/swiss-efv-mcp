import httpx
import pytest
import respx

from swiss_efv_mcp.client import DATASETS, EFVClient
from swiss_efv_mcp.server import (
    budget_impl,
    dimensions_impl,
    headline_impl,
    institution_impl,
    status_impl,
)
from tests.conftest import FIXTURES


def _mock_all():
    for key, csv_text in FIXTURES.items():
        respx.get(DATASETS[key].url).mock(return_value=httpx.Response(200, text=csv_text))


@respx.mock
async def test_headline_happy_and_na_cleaning():
    _mock_all()
    c = EFVClient()
    res = await headline_impl(c, variable="saldo", household="bund", model="fs")
    years = [p.year for p in res.points]
    assert years == [2021, 2022, 2029]  # sorted, NA row dropped
    assert res.points[0].value == 1000.0
    assert res.points[0].is_projection is False  # 2021 settled
    assert res.points[-1].kind == "Budget/financial plans"
    assert res.points[-1].is_projection is True  # 2029 forward-looking
    assert res.provenance == "dump"


@respx.mock
async def test_headline_year_filter_and_household():
    _mock_all()
    c = EFVClient()
    res = await headline_impl(c, "saldo", household="ktn", model="fs", year_from=2022)
    assert [p.year for p in res.points] == [2022]
    assert res.points[0].value == 99.0


@respx.mock
async def test_retry_on_503_then_success():
    # First 503, then 200 — retry must recover.
    route = respx.get(DATASETS["headline"].url).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, text=FIXTURES["headline"]),
        ]
    )
    c = EFVClient(backoff_base=0)
    res = await headline_impl(c, "saldo")
    assert route.call_count == 2
    assert len(res.points) == 3


@respx.mock
async def test_timeout_raises_without_cache():
    respx.get(DATASETS["headline"].url).mock(side_effect=httpx.ConnectError("boom"))
    c = EFVClient(backoff_base=0)
    with pytest.raises(RuntimeError):
        await headline_impl(c, "saldo")


@respx.mock
async def test_retry_exhaustion_message_names_type_and_host():
    # httpx timeout/connect errors carry an empty str(); interpolating only the
    # message used to yield a bare "Upstream unreachable after retries:" that
    # said nothing. The type and host must survive an empty message.
    respx.get(DATASETS["headline"].url).mock(side_effect=httpx.ConnectTimeout(""))
    c = EFVClient(backoff_base=0)
    with pytest.raises(RuntimeError) as exc_info:
        await c.load("headline")
    msg = str(exc_info.value)
    assert "ConnectTimeout" in msg
    assert "www.data.finance.admin.ch" in msg
    assert not msg.rstrip().endswith(":")
    assert isinstance(exc_info.value.__cause__, httpx.ConnectTimeout)


@respx.mock
async def test_status_reports_degraded_after_error():
    respx.get(DATASETS["headline"].url).mock(side_effect=httpx.ConnectError("boom"))
    c = EFVClient(backoff_base=0)
    with pytest.raises(RuntimeError):
        await c.load("headline")
    report = status_impl(c)
    assert report.healthy is False
    assert "headline" in report.message


@respx.mock
async def test_budget_breakdown_level_filter():
    _mock_all()
    c = EFVClient()
    res = await budget_impl(c, topic="Ausgaben nach Aufgabengebiet", year=2024, level=2)
    labels = [i.label for i in res.items]
    assert labels == ["Soziale Wohlfahrt", "Finanzen und Steuern"]  # sorted desc by value
    assert res.items[0].value == 32000.0


@respx.mock
async def test_institution_filter():
    _mock_all()
    c = EFVClient()
    res = await institution_impl(c, departement="Bund", variable="Personalausgaben")
    assert [p.year for p in res.points] == [2007, 2008]


@respx.mock
async def test_dimensions_distinct():
    _mock_all()
    c = EFVClient()
    dims = await dimensions_impl(c)
    assert "saldo" in dims.headline_variables
    assert "bund" in dims.households
    assert "NA" not in dims.households  # cleaned
    assert "Ausgaben nach Aufgabengebiet" in dims.budget_topics


@respx.mock
async def test_cache_second_call_is_cached():
    route = respx.get(DATASETS["headline"].url).mock(
        return_value=httpx.Response(200, text=FIXTURES["headline"])
    )
    c = EFVClient()
    await headline_impl(c, "saldo")
    res2 = await headline_impl(c, "saldo")
    assert route.call_count == 1  # served from cache
    assert res2.provenance == "cached"
