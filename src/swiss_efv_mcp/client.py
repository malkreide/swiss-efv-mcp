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
import time
from dataclasses import dataclass, field
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


@dataclass
class _CacheEntry:
    fetched_at: float
    rows: list[dict[str, str]]


@dataclass
class EFVClient:
    """Thin async client with retry, UA injection and TTL cache."""

    timeout: float = 60.0
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

    async def _fetch_with_retry(self, http: httpx.AsyncClient, url: str) -> httpx.Response:
        assert_host_allowed(url)  # SEC-021: enforce egress allow-list before any request
        last_error: Exception | None = None
        for attempt in range(4):
            if attempt > 0:
                await asyncio.sleep(self.backoff_base**attempt)  # 2s, 4s, 8s in prod
            try:
                resp = await http.get(url)
                # SEC-004: a redirect must not smuggle egress off the allow-list.
                assert_host_allowed(str(resp.url))
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
        assert last_error is not None
        raise RuntimeError(f"Upstream unreachable after retries: {last_error}")

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
