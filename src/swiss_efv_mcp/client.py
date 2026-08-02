"""Data-access layer for the Swiss federal finance (EFV) dump files.

Architecture C (Dump-first): the EFV publishes static CSV dumps behind its
FS/GFS dashboard. There is no filtered query API, so this layer fetches whole
files, cleans them, caches them in memory with a TTL, and lets the tool layer
slice them.

Live-probe findings baked in here (verified 2026-07-24):
- opendata.swiss and efv.admin.ch returned HTTP 403 without a browser
  User-Agent. **No longer true** — re-measured 2026-07-31, both hosts answer an
  honest User-Agent, curl, and a request with no UA header at all. See the note
  at ``_UA``.
- The opendata.swiss "CSV" URLs for two datasets point to an HTML landing page;
  the real files live on a DAM path (``/dam/de/sd-web/{id}/{name}_de.csv``) whose
  opaque id may rotate when EFV re-uploads. Kept here explicitly.
- ``NA`` appears as a literal string in ``hh`` / ``model`` / ``source`` columns
  and must be treated as missing.
"""

from __future__ import annotations

import asyncio
import csv
import io
import ipaddress
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from . import __version__
from .logging_config import get_logger

_log = get_logger(__name__)

# --- Egress allow-list (SEC-021 / SEC-004) ----------------------------------
# The server reaches exactly two EFV hosts. The allow-list is an immutable
# module-level frozenset — not configurable or mutable at runtime — and is
# asserted before every outbound request, so a bug or an injected URL can never
# reach any other host. See docs/network-egress.md.
ALLOWED_HOSTS = frozenset(
    {
        "www.data.finance.admin.ch",
        "www.efv.admin.ch",
    }
)


def assert_host_allowed(url: str) -> None:
    """Reject non-HTTPS URLs, IP-literal hosts, and any host outside
    :data:`ALLOWED_HOSTS` (SEC-004 / SEC-021).

    Called before every request *and* on the final URL after redirects, so a
    redirect can never smuggle egress to a disallowed host.
    """
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ValueError(f"Refusing non-HTTPS egress: {parts.scheme!r}")
    host = parts.hostname
    if host is None:
        raise ValueError("Refusing egress to a URL without a host")
    # No IP literals — the allow-list is hostname-based; an IP literal would be
    # a sign of DNS-rebinding or a crafted URL.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # not an IP literal — good
    else:
        raise ValueError(f"Refusing egress to an IP literal: {host!r}")
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Host not on egress allow-list: {host!r}")


# --- Attribution / provenance (portfolio standard) --------------------------

ATTRIBUTION = (
    "Data: Eidgenoessische Finanzverwaltung EFV — opendata.swiss "
    "(OGD Schweiz, frei nutzbar). Private, non-affiliated project. "
    "Kein Anspruch auf Vollstaendigkeit."
)

# Up to 0.3.0 this sent a spoofed Chrome User-Agent, on the note that the
# endpoints 403 anything else (measured 2026-07-24).
#
# Re-measured 2026-07-31 against all three dataset URLs on both hosts, with
# four User-Agents each — Chrome, this honest one, `curl/8.5.0`, and no UA
# header at all. Every request answered 200/206; the honest UA was then
# repeated three times across all three datasets, nine of nine successful.
# Whatever was rejecting non-browser clients is no longer doing so.
#
# So the server says who it is. A spoofed UA costs the operator the ability to
# recognise us in their logs and to reach us if we misbehave — a price worth
# paying only for a restriction that actually exists. Should EFV start
# filtering again, restore a browser UA *and update this note*; a stale
# justification is how this one survived unexamined.
_UA = f"swiss-efv-mcp/{__version__} (+https://github.com/malkreide/swiss-efv-mcp)"

_DATA_FINANCE = "https://www.data.finance.admin.ch/static/assets/datasets"
_DAM = "https://www.efv.admin.ch/dam/de/sd-web"


@dataclass(frozen=True)
class Dataset:
    key: str
    url: str
    approx_bytes: int
    note: str


# Registry of the *serveable* (small) files only. The 157 MB / 1.23 GB detail
# cubes are deliberately NOT here — see README "Known limitations".
DATASETS: dict[str, Dataset] = {
    "headline": Dataset(
        "headline",
        f"{_DATA_FINANCE}/fs_dashboard/main_extern.csv",
        516_025,
        "Hauptaggregate und Prognosen, hh x model x variable x jahr, 1990-2029",
    ),
    "budget": Dataset(
        "budget",
        f"{_DAM}/m9aWXSnsRvNO/bundeshaushalt_de.csv",
        5_055_334,
        "Gesamthaushalt Bund, hierarchisch (bis 8 Ebenen), DE-Labels inline",
    ),
    "institutions": Dataset(
        "institutions",
        f"{_DAM}/LheAU2Ioeux7/institutionen_de.csv",
        1_041_656,
        "Ausgaben nach Departement/Verwaltungseinheit ab 2007",
    ),
}

# Values that mean "missing" in EFV administrative CSVs.
_NULLISH = {"", "NA", "N/A", "null", "None"}

_CACHE_TTL_SECONDS = 24 * 3600

# --- Retry policy (ARCH-014) ------------------------------------------------
# Three questions the retry has to answer: *what* is retried, *how fast*, and
# *how long*. The first is settled below (4xx except 429 fails fast); these
# constants settle the other two.

_ATTEMPTS = 4

# Ceiling on the *whole* call — every attempt, every wait, together.
#
# An attempt count is not a bound: four attempts at a 60s per-request timeout
# plus backoff are over four minutes, and the number never says so. Worse, the
# relevant limit is not ours. The caller has its own timeout, and past it
# nobody is listening any more — the work continues, the load lands on the
# source, and the result goes nowhere.
#
# The anchor is measured, not guessed: the Python MCP SDK ships
# ``MCP_DEFAULT_TIMEOUT = 30.0`` for general operations
# (``mcp/shared/_httpx_utils.py``). 25s leaves headroom for MCP framing, CSV
# parsing and the tool layer on top of the fetch.
#
# The trade-off is real and deliberate: a slow first attempt can now consume
# the budget and leave no room for a retry. That is the intended answer — a
# retry that finishes after the caller gave up buys nothing and costs the
# source a request.
_TOTAL_BUDGET_SECONDS = 25.0

# Ceiling for a single wait. Guards two things at once: an exponential ladder
# that would otherwise grow without bound, and a `Retry-After` value the source
# is entitled to send but we are not obliged to sit through. A dump that is 20
# seconds away is better refused than waited for — the caller has its own
# timeout.
_MAX_DELAY_SECONDS = 20.0

# Jitter spread. Without it every client that hit the same outage retries in
# lockstep, and the load returns as a wave exactly when the source recovers —
# the retry storm extends the outage it was meant to bridge.
_JITTER_SPREAD = 0.5  # exponential delays land in [0.5x, 1.5x]

# Applied on top of a `Retry-After` value, and deliberately one-sided: the
# source told us when to come back, so coming back *later* is fine and coming
# back *earlier* is not.
_RETRY_AFTER_JITTER = 0.25  # lands in [1.0x, 1.25x]

# Statuses that carry a meaningful `Retry-After` (RFC 9110 §10.2.3). A 429 or a
# 503 is the source saying "not now, try at T" — an answer to the very question
# the backoff curve is guessing at.
_RETRY_AFTER_STATUSES = frozenset({429, 503})


def parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Seconds to wait per the response's ``Retry-After``, or None.

    RFC 9110 §10.2.3 allows two forms: delta-seconds (``120``) and an HTTP-date
    (``Wed, 21 Oct 2026 07:28:00 GMT``). Both appear in the wild, so both are
    read. Anything unparseable yields None and the caller falls back to its own
    curve — a malformed header must not become a crash on the error path.
    """
    if resp is None or resp.status_code not in _RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # RFC 9110 dates are GMT; a naive one means UTC
        when = when.replace(tzinfo=UTC)
    # Never negative: a date in the past means "now".
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


@dataclass
class _CacheEntry:
    fetched_at: float
    rows: list[dict[str, str]]


@dataclass
class EFVClient:
    """Thin async client with retry, UA injection and TTL cache."""

    # Per-operation ceiling (connect, read, write, pool) — httpx applies it to
    # each, not to the call as a whole. `total_budget` is what bounds the whole
    # call; the effective per-attempt timeout is the smaller of the two.
    timeout: float = 25.0
    total_budget: float = _TOTAL_BUDGET_SECONDS
    backoff_base: float = 2.0  # tests set 0 for instant retries
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)
    _last_error: dict[str, str] = field(default_factory=dict)
    _http: httpx.AsyncClient | None = field(default=None, repr=False)

    def _client(self) -> httpx.AsyncClient:
        """Return a shared, lazily-created httpx client (SDK-001).

        One connection pool is reused across all requests rather than opening a
        fresh client per dump. Closed on shutdown via :meth:`aclose`.
        """
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=self.timeout, headers={"User-Agent": _UA}, follow_redirects=True
            )
        return self._http

    async def aclose(self) -> None:
        """Close the shared client. Wired to the FastMCP lifespan."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    def _delay(self, attempt: int, last_error: Exception | None) -> float:
        """Seconds to wait before ``attempt`` (ARCH-014).

        The source's own answer beats our guess: if it sent ``Retry-After`` on a
        429 or 503, that value wins over the exponential curve. Everything is
        capped and spread — see the constants above for why each matters.
        """
        hinted = parse_retry_after(getattr(last_error, "response", None))
        if hinted is not None:
            jittered = hinted * (1.0 + random.random() * _RETRY_AFTER_JITTER)
        else:
            jittered = self.backoff_base**attempt * (
                1.0 - _JITTER_SPREAD + random.random() * 2 * _JITTER_SPREAD
            )
        # Cap *after* jitter. The other order made `_MAX_DELAY_SECONDS` not a
        # bound at all: a value capped at 20s was then multiplied by up to 1.5
        # and landed at 30s. The constant claimed a ceiling it did not hold.
        return min(jittered, _MAX_DELAY_SECONDS)

    async def _fetch_with_retry(self, http: httpx.AsyncClient, url: str) -> httpx.Response:
        assert_host_allowed(url)  # SEC-021: enforce egress allow-list before any request
        deadline = time.monotonic() + self.total_budget
        last_error: Exception | None = None
        attempts = 0
        for attempt in range(_ATTEMPTS):
            if attempt > 0:
                delay = self._delay(attempt, last_error)
                # A wait that outlasts the budget is a wait for nobody: the
                # caller has given up by the time it ends. Stop instead.
                if delay >= deadline - time.monotonic():
                    break
                await asyncio.sleep(delay)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            attempts += 1
            try:
                # httpx applies its timeout per operation (connect/read/write/
                # pool) and the read timeout restarts with every chunk — that
                # bounds each step, not the call, so a slowly trickling response
                # could outlast the budget without any single read timing out.
                # `asyncio.timeout` is the wall-clock deadline the budget
                # actually promises; the httpx timeout stays alongside it as the
                # finer per-operation bound.
                async with asyncio.timeout(remaining):
                    resp = await http.get(url, timeout=min(self.timeout, remaining))
                    # SEC-004: a redirect must not smuggle egress off the allow-list.
                    assert_host_allowed(str(resp.url))
                    resp.raise_for_status()
                    return resp
            except TimeoutError as exc:  # budget gone, not just this attempt
                last_error = exc
                break
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
        if last_error is None:  # budget gone before a single request went out
            raise RuntimeError(
                f"Upstream not attempted: {self.total_budget:g}s budget already spent "
                f"(host={urlsplit(url).hostname})"
            )
        # httpx timeout/connect errors carry an *empty* ``str()`` — interpolating
        # only the message produced a bare "Upstream unreachable after retries:"
        # that named neither the failure mode nor the host. Always report the
        # exception type and the host so a transient outage is distinguishable
        # from a broken URL at a glance.
        #
        # Which limit ran out is part of that: "all 4 attempts used" and "the
        # budget ran out after 2" call for different fixes — more patience in
        # the first case, a faster source or a wider budget in the second.
        why = (
            f"all {_ATTEMPTS} attempts used"
            if attempts >= _ATTEMPTS
            else f"{self.total_budget:g}s budget spent"
        )
        detail = str(last_error) or "no further detail"
        raise RuntimeError(
            f"Upstream unreachable after {attempts} attempt(s), {why}: "
            f"{type(last_error).__name__}: {detail} (host={urlsplit(url).hostname})"
        ) from last_error

    async def load(self, key: str) -> tuple[list[dict[str, str]], str]:
        """Return (rows, provenance). provenance is 'cached' or 'dump'."""
        ds = DATASETS[key]
        now = time.time()
        cached = self._cache.get(key)
        if cached and (now - cached.fetched_at) < _CACHE_TTL_SECONDS:
            return cached.rows, "cached"

        http = self._client()
        try:
            resp = await self._fetch_with_retry(http, ds.url)
        except Exception as exc:  # noqa: BLE001 — surfaced via status(), not raised blindly
            # OBS-002: log full detail to stderr; surface only a masked,
            # model-safe message (exception *type*, no upstream body).
            _log.warning(
                "dump_fetch_failed", dataset=key, error_type=type(exc).__name__, exc_info=exc
            )
            self._last_error[key] = f"upstream fetch failed ({type(exc).__name__})"
            if cached:  # stale-but-alive beats nothing
                return cached.rows, "cached"
            raise

        rows = list(csv.DictReader(io.StringIO(resp.text)))
        self._cache[key] = _CacheEntry(now, rows)
        self._last_error.pop(key, None)
        return rows, "dump"

    def status(self) -> dict[str, dict[str, str | int | None]]:
        out: dict[str, dict[str, str | int | None]] = {}
        for key, ds in DATASETS.items():
            entry = self._cache.get(key)
            out[key] = {
                "url": ds.url,
                "note": ds.note,
                "cached_rows": len(entry.rows) if entry else None,
                "age_seconds": int(time.time() - entry.fetched_at) if entry else None,
                "last_error": self._last_error.get(key),
            }
        return out


# --- Parsing helpers --------------------------------------------------------


def clean(value: str | None) -> str | None:
    """Map EFV null-ish tokens to None. 'Rom-Ampel'-Schutz."""
    if value is None:
        return None
    v = value.strip()
    return None if v in _NULLISH else v


def to_float(value: str | None) -> float | None:
    v = clean(value)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def to_year(value: str | None) -> int | None:
    v = clean(value)
    if v is None:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


# Live-probe finding: "forward-looking" is not one label. For the Bund, future
# years are "Budget/financial plans" (Voranschlag/Finanzplan); "Forecasts" is
# reserved for the aggregate state (hh=staat). Map both to is_projection so the
# agent never has to know the taxonomy.
_PROJECTION_SOURCES = {"Budget/financial plans", "Forecasts", "Survey budget"}
_ACTUAL_SOURCES = {
    "Financial statements",
    "Provisional financial statements",
    "Data available",
    "Survey financial statements",
}


def is_projection(source: str | None) -> bool | None:
    s = clean(source)
    if s is None:
        return None
    if s in _PROJECTION_SOURCES:
        return True
    if s in _ACTUAL_SOURCES:
        return False
    return None
