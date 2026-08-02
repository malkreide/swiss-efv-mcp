"""Retry policy toward the source (ARCH-014): Retry-After, jitter, cap.

Three properties, each asserted in both directions where that is possible:

1. The source's own answer beats our guess. A ``Retry-After`` on a 429 or 503
   is an explicit instruction; the exponential curve is a guess at the same
   question.
2. Nothing waits without spread. Ten clients that hit the same outage must not
   come back in lockstep the moment the source recovers.
3. Nothing waits unbounded. Neither the ladder nor a `Retry-After` the source
   is entitled to send may hold a tool call open indefinitely.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from swiss_efv_mcp.client import (
    _JITTER_SPREAD,
    _MAX_DELAY_SECONDS,
    _RETRY_AFTER_JITTER,
    DATASETS,
    EFVClient,
    parse_retry_after,
)
from tests.conftest import FIXTURES

URL = DATASETS["headline"].url


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers, request=httpx.Request("GET", URL))


# --- parse_retry_after: pure, no network ------------------------------------


class TestParseRetryAfter:
    def test_delta_seconds(self):
        assert parse_retry_after(_resp(429, "120")) == 120.0

    def test_http_date_in_the_future(self):
        when = datetime.now(UTC) + timedelta(seconds=90)
        got = parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
        assert got is not None
        assert 80 <= got <= 95  # second-resolution header, allow slack

    def test_http_date_in_the_past_means_now(self):
        when = datetime.now(UTC) - timedelta(hours=1)
        assert parse_retry_after(_resp(503, format_datetime(when, usegmt=True))) == 0.0

    def test_absent_header(self):
        assert parse_retry_after(_resp(429)) is None

    def test_malformed_header_does_not_raise(self):
        # A bad header must not turn into a crash on the error path — the
        # caller falls back to its own curve.
        assert parse_retry_after(_resp(429, "next Tuesday")) is None
        assert parse_retry_after(_resp(429, "")) is None
        assert parse_retry_after(_resp(429, "-5")) is None

    def test_ignored_on_other_statuses(self):
        # 500 carries no promise about when to come back.
        assert parse_retry_after(_resp(500, "30")) is None

    def test_no_response_at_all(self):
        # Timeouts and connect errors have no response object.
        assert parse_retry_after(None) is None


# --- delay computation ------------------------------------------------------


class TestDelay:
    def test_retry_after_beats_the_exponential_curve(self):
        # The hinted value is chosen *outside* the curve's reach: attempt 1 with
        # base 2.0 spans [1, 3] seconds, so a delay near 9 can only have come
        # from the header. A test whose band the bare curve also satisfies would
        # pass with the feature removed — and two of these did, before this run.
        c = EFVClient(backoff_base=2.0)
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "9"))
        delay = c._delay(1, exc)
        assert 9.0 <= delay <= 9.0 * (1 + _RETRY_AFTER_JITTER)

    def test_retry_after_is_never_undercut(self):
        """Jitter on a Retry-After is one-sided: later is polite, earlier is not."""
        c = EFVClient(backoff_base=2.0)
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "5"))
        for _ in range(50):
            assert c._delay(1, exc) >= 5.0

    def test_absurd_retry_after_is_capped(self):
        # A day is a value the source may legitimately send; sitting through it
        # is not. Both bounds matter: the upper one proves the cap binds, the
        # lower one proves the header was read at all — without it the bare
        # curve's 2s would satisfy the assertion and the test would prove
        # nothing.
        c = EFVClient(backoff_base=2.0)
        exc = httpx.HTTPStatusError("503", request=None, response=_resp(503, "86400"))
        delay = c._delay(1, exc)
        assert _MAX_DELAY_SECONDS <= delay <= _MAX_DELAY_SECONDS * (1 + _RETRY_AFTER_JITTER)

    def test_exponential_ladder_is_capped(self):
        c = EFVClient(backoff_base=10.0)  # 10**3 = 1000s without a cap
        assert c._delay(3, None) <= _MAX_DELAY_SECONDS * (1 + _JITTER_SPREAD)

    def test_delay_is_spread(self):
        """Without jitter every client retries in lockstep. Two draws must differ."""
        c = EFVClient(backoff_base=2.0)
        draws = {c._delay(2, None) for _ in range(30)}
        assert len(draws) > 1, "delay is deterministic — jitter is not applied"
        base = 2.0**2
        assert all(
            base * (1 - _JITTER_SPREAD) <= d <= base * (1 + _JITTER_SPREAD) for d in draws
        )

    def test_zero_backoff_base_stays_instant(self):
        """Tests set backoff_base=0; jitter must not reintroduce a wait."""
        c = EFVClient(backoff_base=0)
        assert all(c._delay(a, None) == 0.0 for a in (1, 2, 3))


# --- end to end through the retry loop --------------------------------------


@respx.mock
async def test_retry_after_is_honoured_by_the_loop(monkeypatch):
    """The value the source sent must reach asyncio.sleep, not the curve."""
    slept: list[float] = []

    async def _capture(seconds):
        slept.append(seconds)

    monkeypatch.setattr("swiss_efv_mcp.client.asyncio.sleep", _capture)
    respx.get(URL).mock(
        side_effect=[
            _resp(429, "3"),
            httpx.Response(200, text=FIXTURES["headline"]),
        ]
    )
    c = EFVClient(backoff_base=2.0)
    rows, _ = await c.load("headline")
    assert rows
    assert len(slept) == 1
    assert 3.0 <= slept[0] <= 3.0 * (1 + _RETRY_AFTER_JITTER)


@respx.mock
async def test_429_without_header_falls_back_to_the_curve(monkeypatch):
    slept: list[float] = []

    async def _capture(seconds):
        slept.append(seconds)

    monkeypatch.setattr("swiss_efv_mcp.client.asyncio.sleep", _capture)
    respx.get(URL).mock(
        side_effect=[_resp(429), httpx.Response(200, text=FIXTURES["headline"])]
    )
    c = EFVClient(backoff_base=2.0)
    await c.load("headline")
    assert len(slept) == 1
    assert 2.0 * (1 - _JITTER_SPREAD) <= slept[0] <= 2.0 * (1 + _JITTER_SPREAD)


@respx.mock
async def test_404_still_fails_fast_without_waiting(monkeypatch):
    """ARCH-014: 4xx except 429 is a statement about the request, not the moment."""
    slept: list[float] = []

    async def _capture(seconds):
        slept.append(seconds)

    monkeypatch.setattr("swiss_efv_mcp.client.asyncio.sleep", _capture)
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    c = EFVClient(backoff_base=2.0)
    with pytest.raises(httpx.HTTPStatusError):
        await c.load("headline")
    assert route.call_count == 1
    assert slept == []


def test_http_client_does_not_retry_on_its_own_level():
    """ARCH-014: exactly one level may retry. Transport retries stack multiplicatively."""
    c = EFVClient()
    transport = c._client()._transport
    assert getattr(transport, "_pool", None) is not None
    assert transport._pool._retries == 0
