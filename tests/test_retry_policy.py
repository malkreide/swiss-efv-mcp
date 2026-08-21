"""Retry policy toward the source (ARCH-014): Retry-After, jitter, cap.

Three properties, each asserted in both directions where that is possible:

1. The source's own answer beats our guess. A ``Retry-After`` on a 429 or 503
   is an explicit instruction; the exponential curve is a guess at the same
   question.
2. Nothing waits without spread. Ten clients that hit the same outage must not
   come back in lockstep the moment the source recovers.
3. Nothing waits unbounded. Neither the ladder nor a `Retry-After` the source
   is entitled to send may hold a tool call open indefinitely.

The wait and the clock are taken over through `client._sleep` and
`client._monotonic` — the module's own names — never through
`client.asyncio.sleep` or `client.time.monotonic`. Those two read as local
overrides and are not: `client.asyncio` *is* the stdlib module, so the
replacement holds for the whole process. For the clock that is not cosmetic —
see `test_die_fake_uhr_laesst_die_frist_der_event_loop_laufen`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from swiss_efv_mcp import client as client_mod
from swiss_efv_mcp.client import (
    _ATTEMPTS,
    _JITTER_SPREAD,
    _MAX_DELAY_SECONDS,
    _RETRY_AFTER_JITTER,
    _TOTAL_BUDGET_SECONDS,
    DATASETS,
    EFVClient,
    UpstreamError,
    UpstreamNotAttemptedError,
    parse_retry_after,
)
from tests.conftest import FIXTURES

URL = DATASETS["headline"].url

# Wall-clock numbers for the deadline test below, spread far enough apart that
# scheduler jitter cannot move the outcome. Measured on 3.11 over 15 runs of
# that test's own body: it returned in 0.100-0.117s against a 0.05s budget, so
# roughly 0.055s of the elapsed time is client setup plus the one attempt, not
# the budget. The old bound of 0.5s left about 0.4s of absolute headroom - and
# CI jitter is absolute, not proportional: a loaded runner turned 0.105s into
# 0.55s and the assertion fell. Raising the budget does not shrink the jitter,
# it makes the jitter small *relative to* what is measured, so a deadline that
# fails to cut now misses by seconds rather than by milliseconds.
_BUDGET = 0.5
_CUT_BY = 2.5
_SLOW_RESPONSE = 8.0


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
        # Exactly the cap, not "the cap times jitter": capping happens after
        # jitter, otherwise `_MAX_DELAY_SECONDS` would not be a bound at all.
        # Equality still discriminates — the bare curve gives 2s here.
        c = EFVClient(backoff_base=2.0)
        exc = httpx.HTTPStatusError("503", request=None, response=_resp(503, "86400"))
        assert c._delay(1, exc) == _MAX_DELAY_SECONDS

    def test_exponential_ladder_is_capped(self):
        c = EFVClient(backoff_base=10.0)  # 10**3 = 1000s without a cap
        for _ in range(30):
            assert c._delay(3, None) <= _MAX_DELAY_SECONDS

    def test_the_cap_is_a_real_bound_not_a_midpoint(self):
        """`_MAX_DELAY_SECONDS` must hold even when jitter swings up.

        Capping before jitter let a 20s ceiling grow to 30s on the exponential
        path and 25s on the `Retry-After` path — the constant claimed a bound it
        did not hold. Found by a Codex review on `parlament-mcp#35`, on the same
        pattern this file introduced.
        """
        c = EFVClient(backoff_base=10.0)
        exc = httpx.HTTPStatusError("429", request=None, response=_resp(429, "86400"))
        for attempt in range(1, 6):
            for _ in range(20):
                assert c._delay(attempt, None) <= _MAX_DELAY_SECONDS
                assert c._delay(attempt, exc) <= _MAX_DELAY_SECONDS

    def test_delay_is_spread(self):
        """Without jitter every client retries in lockstep. Two draws must differ."""
        c = EFVClient(backoff_base=2.0)
        draws = {c._delay(2, None) for _ in range(30)}
        assert len(draws) > 1, "delay is deterministic — jitter is not applied"
        base = 2.0**2
        assert all(base * (1 - _JITTER_SPREAD) <= d <= base * (1 + _JITTER_SPREAD) for d in draws)

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

    monkeypatch.setattr(client_mod, "_sleep", _capture)
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

    monkeypatch.setattr(client_mod, "_sleep", _capture)
    respx.get(URL).mock(side_effect=[_resp(429), httpx.Response(200, text=FIXTURES["headline"])])
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

    monkeypatch.setattr(client_mod, "_sleep", _capture)
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


# --- total budget (ARCH-014) ------------------------------------------------


@pytest.fixture
def fake_clock(monkeypatch):
    """A clock that only advances when the client sleeps.

    Without it the budget can never run out in a test: patched-out sleeps take
    no wall-clock time, so ``time.monotonic()`` never moves and every deadline
    holds forever. The test would then pass whatever the budget logic did.
    """
    now = {"t": 1000.0}
    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)
        now["t"] += seconds

    monkeypatch.setattr(client_mod, "_monotonic", lambda: now["t"])
    monkeypatch.setattr(client_mod, "_sleep", _sleep)
    return {"advance": lambda s: now.update(t=now["t"] + s), "slept": slept}


@respx.mock
async def test_budget_cuts_the_ladder_short(fake_clock):
    """Fewer than _ATTEMPTS requests go out once the waits would outlast the budget."""
    route = respx.get(URL).mock(side_effect=httpx.ConnectTimeout(""))
    c = EFVClient(backoff_base=10.0, total_budget=12.0)  # waits 5-15s, 50-150s, ...
    with pytest.raises(RuntimeError) as exc_info:
        await c.load("headline")
    assert route.call_count < _ATTEMPTS, "budget did not bound the ladder"
    assert route.call_count >= 1, "the first attempt must always go out"
    assert "budget spent" in str(exc_info.value)
    assert "12s" in str(exc_info.value)


@respx.mock
async def test_full_ladder_runs_when_the_budget_allows(fake_clock):
    """Counter-direction: a wide budget must not cut anything short."""
    route = respx.get(URL).mock(side_effect=httpx.ConnectTimeout(""))
    c = EFVClient(backoff_base=2.0, total_budget=600.0)
    with pytest.raises(RuntimeError) as exc_info:
        await c.load("headline")
    assert route.call_count == _ATTEMPTS
    assert "all 4 attempts used" in str(exc_info.value)


@respx.mock
async def test_per_attempt_timeout_is_clamped_to_the_remaining_budget(fake_clock):
    """A single attempt may not be granted more time than the budget has left."""
    route = respx.get(URL).mock(return_value=httpx.Response(200, text=FIXTURES["headline"]))
    c = EFVClient(timeout=25.0, total_budget=4.0)
    await c.load("headline")
    sent = route.calls.last.request.extensions["timeout"]
    assert sent["read"] == pytest.approx(4.0), sent


@respx.mock
async def test_budget_does_not_touch_the_happy_path(fake_clock):
    route = respx.get(URL).mock(return_value=httpx.Response(200, text=FIXTURES["headline"]))
    rows, prov = await EFVClient().load("headline")
    assert rows and prov == "dump"
    assert route.call_count == 1
    assert fake_clock["slept"] == []


def test_default_budget_stays_under_the_mcp_client_default():
    """The budget is only meaningful relative to the caller's own timeout.

    ``MCP_DEFAULT_TIMEOUT`` is what the Python MCP SDK grants a general
    operation. A budget at or above it would let the server work past the point
    where its answer can still be delivered.
    """
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    assert _TOTAL_BUDGET_SECONDS < MCP_DEFAULT_TIMEOUT
    assert EFVClient().timeout <= _TOTAL_BUDGET_SECONDS


# --- The seams themselves ---------------------------------------------------
#
# The three tests below guard what the tests above stand on. Without them the
# fixtures could go back to patching the stdlib module and every assertion here
# would stay green while checking less than it claims.


def test_die_beiden_nahtstellen_gehoeren_dem_modul():
    """`_sleep` and `_monotonic` must be what the retry loop actually calls.

    Read off the source, not off behaviour: a loop that goes back to
    `asyncio.sleep(delay)` still passes every test above, because the fixture
    then patches the stdlib function those tests observe. The difference only
    shows in what *else* the patch takes down with it.
    """
    import inspect

    quelle = inspect.getsource(EFVClient._fetch_with_retry)
    assert "await _sleep(" in quelle, "the retry loop no longer waits through the alias"
    assert "asyncio.sleep" not in quelle, "back on the stdlib function — patching it is global"
    assert "time.monotonic" not in quelle, "back on the stdlib clock — patching it stops the loop"
    assert "_monotonic()" in quelle, "the budget reads a clock the module does not own"


async def test_das_uebernehmen_der_naht_laesst_den_prozess_in_ruhe(monkeypatch):
    """Patching the seam must not replace the function for everyone else.

    `monkeypatch.setattr("swiss_efv_mcp.client.asyncio.sleep", ...)` resolves
    `client.asyncio` to the stdlib module and swaps `sleep` there — visible to
    httpx, respx, anyio and every other test running in this process. The alias
    is a name of this module; taking it over reaches exactly this loop.
    """
    import asyncio
    import time

    vorher_sleep, vorher_uhr = asyncio.sleep, time.monotonic

    async def _nichts(_seconds: float) -> None:
        pass

    monkeypatch.setattr(client_mod, "_sleep", _nichts)
    monkeypatch.setattr(client_mod, "_monotonic", lambda: 0.0)
    assert client_mod._sleep is _nichts, "the seam was not taken over at all"
    assert asyncio.sleep is vorher_sleep, "asyncio.sleep was replaced process-wide"
    assert time.monotonic is vorher_uhr, "time.monotonic was replaced process-wide"


async def test_die_fake_uhr_laesst_die_frist_der_event_loop_laufen(fake_clock):
    """The clock the budget's `asyncio.timeout` runs on must keep running.

    This is the assurance that was impossible before. The event loop reads
    `time.monotonic` from the same module object, so freezing it there froze
    `loop.time()` — and an `asyncio.timeout` scheduled under a stopped clock
    waits for a moment that never arrives. The budget's wall-clock deadline in
    `_fetch_with_retry` was therefore out of force in exactly the tests written
    to check the budget, and nothing said so: they were green.

    Falls the moment the fake clock reaches past this module again.
    """
    import asyncio

    loop = asyncio.get_running_loop()
    vorher = loop.time()
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await asyncio.sleep(5.0)
    verstrichen = loop.time() - vorher
    assert 0.01 < verstrichen < 1.0, (
        f"the loop clock advanced by {verstrichen} — not by real elapsed time"
    )
    assert fake_clock["slept"] == [], "the client did not run here; only the loop was measured"


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline():
    """The budget must bind even when the httpx timeout never fires.

    httpx applies its timeout per operation and the read timeout restarts with
    every chunk, so a slowly trickling response can outlast the total budget
    without any single read timing out. The comment above `timeout` in
    `client.py` said exactly that — and the budget was advertised anyway.

    Deliberately without `fake_clock`: this guarantee is about real time, and a
    clock that only moves when something sleeps cannot refute it. That blind
    spot is why the counter-checks missed this.

    The margins are wide on purpose — see `_BUDGET` above for the measurement
    that set them. A warm-up call pays the client's setup cost before the clock
    starts, so the measured window holds the deadline and nothing else.
    """
    import asyncio as real_asyncio
    import time as real_time

    # Warm-up on a full budget: builds the client, opens the transport and pays
    # whatever else the first call through respx costs, all outside the window
    # measured below.
    route = respx.get(URL).mock(return_value=httpx.Response(200, text=FIXTURES["headline"]))
    warm = EFVClient()
    await warm.load("headline")
    await warm.aclose()

    async def _slow(request):
        await real_asyncio.sleep(_SLOW_RESPONSE)
        return httpx.Response(200, text=FIXTURES["headline"])

    route.mock(side_effect=_slow)
    c = EFVClient(total_budget=_BUDGET)
    started = real_time.monotonic()
    with pytest.raises(RuntimeError):
        await c.load("headline")
    elapsed = real_time.monotonic() - started

    # Two-sided on purpose. The upper bound is the guarantee: a response that
    # would have taken _SLOW_RESPONSE was cut. The lower bound says the cut came
    # from the budget rather than from something failing straight away — a
    # deadline computed wrong sails through an upper bound alone.
    assert elapsed >= _BUDGET / 2, f"cut too early to be the budget: {elapsed:.3f}s"
    assert elapsed < _CUT_BY, f"deadline did not cut: {elapsed:.2f}s"
    await c.aclose()


# --- The error is typed, not bare -------------------------------------------
#
# `reference/adoption.toml` in mcp-data-source-probe-skill declares
# `no_bare_runtime_error` — "fails with a typed upstream error a caller can
# branch on" — as a property every adoption of the retry template must hold.
# Read against the servers on 2026-08-07, this module was the ONE that did not:
# it raised `RuntimeError` twice while being cited as the model the template was
# repaired against. These two tests are what stops that from coming back.


@respx.mock
async def test_exhaustion_raises_a_typed_error_not_a_bare_runtime_error():
    """A bare RuntimeError is indistinguishable from a bug in this server.

    That is the entire cost of the defect: a caller that wants to serve a stale
    cache when the source is down cannot tell "the source is down" from "we have
    a defect", so it catches both or neither.
    """
    respx.get(DATASETS["headline"].url).mock(side_effect=httpx.ConnectTimeout(""))
    c = EFVClient(backoff_base=0)
    with pytest.raises(UpstreamError) as exc_info:
        await c.load("headline")
    assert type(exc_info.value) is UpstreamError, "must not be a bare RuntimeError"
    # Still a RuntimeError subclass — the change is additive, and every existing
    # `except RuntimeError` keeps working.
    assert isinstance(exc_info.value, RuntimeError)


@respx.mock
async def test_a_spent_budget_before_the_first_request_has_its_own_type(fake_clock):
    """Nothing was asked of the source, so this says nothing about its health.

    A caller retrying on `UpstreamError` would be retrying a timeout that never
    reached the network — hence the distinct type.
    """
    respx.get(DATASETS["headline"].url).mock(side_effect=httpx.ConnectTimeout(""))
    c = EFVClient(backoff_base=0, total_budget=0.0)
    with pytest.raises(UpstreamNotAttemptedError) as exc_info:
        await c.load("headline")
    assert isinstance(exc_info.value, UpstreamError)
    assert "budget already spent" in str(exc_info.value)


# --- The scheduled live suite gets its own budget ---------------------------
#
# Production and monitor answer to different callers. The tests below hold the
# distinction: that the monitor really gets its ladder, that production really
# does not, and that the monitor's worst case still fits the job it runs in.


def _haengende_quelle(fake_clock):
    """A source that never answers, modelled in the fake clock's time.

    The attempt consumes exactly the time it was granted — `request.extensions`
    carries the per-attempt timeout the retry loop computed, i.e.
    ``min(timeout, remaining)`` — and only then fails. Without advancing the
    clock, `respx` would raise instantly and every budget would look wide
    enough: the very property under test would be invisible.
    """

    def _seite(request):
        gewaehrt = request.extensions["timeout"]["read"]
        fake_clock["advance"](gewaehrt)
        raise httpx.ConnectTimeout("", request=request)

    return _seite


@respx.mock
async def test_die_live_suite_bekommt_ihre_vier_versuche(fake_clock):
    """A hanging connect must not eat the monitor's whole ladder in one attempt."""
    from tests.test_live import live_client

    route = respx.get(URL).mock(side_effect=_haengende_quelle(fake_clock))
    with pytest.raises(UpstreamError) as exc_info:
        await live_client().load("headline")
    assert route.call_count == _ATTEMPTS, (
        f"the live budget left room for {route.call_count} of {_ATTEMPTS} attempts"
    )
    assert "all 4 attempts used" in str(exc_info.value)


@respx.mock
async def test_die_produktionsvorgabe_kaeme_hier_auf_einen_versuch(fake_clock):
    """The counter-direction, and the reason the suite needed its own budget.

    Not a defect in production: a retry that finishes after the MCP caller gave
    up buys nothing. It is the wrong bound for a cron job, and this test is
    what keeps the monitor from silently inheriting it again.
    """
    route = respx.get(URL).mock(side_effect=_haengende_quelle(fake_clock))
    with pytest.raises(UpstreamError) as exc_info:
        await EFVClient(backoff_base=1.0).load("headline")
    assert route.call_count == 1
    assert "budget spent" in str(exc_info.value)


def test_live_budget_fits_the_job_timeout():
    """The two numbers that must agree, in two files that never read each other.

    A failed fetch is not cached, so every live test that needs a dead dataset
    pays the full budget again. Raising the budget therefore spends the job's
    `timeout-minutes`, and a job killed by that timeout writes no JUnit XML at
    all — the run would go from a classified `unknown` to no evidence.
    """
    import pathlib
    import re

    from tests.test_live import _LIVE_TOTAL_BUDGET

    wurzel = pathlib.Path(__file__).resolve().parents[1]
    live_yml = (wurzel / ".github" / "workflows" / "live.yml").read_text(encoding="utf-8")
    treffer = re.search(r"^\s*timeout-minutes:\s*(\d+)", live_yml, re.MULTILINE)
    assert treffer, "live.yml carries no job timeout — nothing bounds the worst case"
    job_sekunden = int(treffer.group(1)) * 60

    live_py = (wurzel / "tests" / "test_live.py").read_text(encoding="utf-8")
    anzahl_tests = len(re.findall(r"^async def test_", live_py, re.MULTILINE))
    assert anzahl_tests > 0, "no live tests found — the worst case would read as zero"

    schlimmstenfalls = _LIVE_TOTAL_BUDGET * anzahl_tests
    assert schlimmstenfalls * 2 <= job_sekunden, (
        f"{anzahl_tests} tests at {_LIVE_TOTAL_BUDGET:g}s is {schlimmstenfalls:g}s — "
        f"too close to the job's {job_sekunden}s. Halve the budget or raise the job timeout."
    )
