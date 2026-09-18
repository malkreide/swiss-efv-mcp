"""FastMCP server exposing Swiss federal finance (EFV) tools.

Business logic lives in ``*_impl`` functions that take an :class:`EFVClient`,
so they are unit-testable with respx without spinning up MCP. The ``@mcp.tool``
wrappers are thin adapters over a module-level client.

Anchor demo query:
    "Wie hat sich der Bundessaldo seit der SNB-Zinswende 2022 entwickelt — und
     in welche Aufgabengebiete floss das Ausgabenwachstum?"
    -> fiscal_headline(variable='saldo', household='bund', 2021..2029)
     + fiscal_budget_breakdown(topic='Ausgaben nach Aufgabengebiet')
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .client import EFVClient, clean, is_projection, to_float, to_year
from .logging_config import get_logger
from .models import (
    BreakdownItem,
    BudgetBreakdown,
    Dimensions,
    HeadlineSeries,
    InstitutionPoint,
    InstitutionSeries,
    Point,
    StatusReport,
)

client = EFVClient()


def _log():
    """Den Logger erst beim Aufruf holen, nie beim Import.

    `get_logger` ruft `configure_logging()` nach, wenn noch nichts konfiguriert
    ist. Stuende der Aufruf auf Modulebene, waere die Konfiguration schon beim
    `from .server import mcp` in `__main__.py` festgelegt — mit der Vorgabe
    `INFO` — und ein spaeteres `configure_logging(settings.log_level)` muesste
    umkonfigurieren koennen, um noch etwas zu bewirken.
    `test_der_eingestellte_log_level_wirkt_trotz_import_reihenfolge` haelt das
    Zusammenspiel fest.
    """
    return get_logger(__name__)


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Own the shared HTTP client; close it cleanly on shutdown (SDK-001)."""
    try:
        yield
    finally:
        await client.aclose()


# Die beiden Protokoll-Aeren, die dieser Server bedient (ARCH-012).
#
# Bis `mcp` 1.x gab es nur eine: jede Verbindung begann mit dem
# `initialize`-Handshake, und ein einzelner Pin genuegte. `mcp` 2.x fuehrt
# daneben die *moderne* Aera `2026-07-28` (SEP-2322) — dort gibt es keinen
# Handshake mehr, sondern `server/discover` und einen Umschlag pro Anfrage.
# `Client.initialize_result` ist auf einer solchen Verbindung `None`; wer
# weiterhin dagegen prueft, prueft eine Aera, die moderne Clients nicht sprechen.
#
# Deshalb ein Paar statt einer Zeichenkette. Beide Werte sind gegen die
# SDK-Konstanten gehalten (`tests/test_protocol_version.py`), und beide werden
# mit einer echten Verbindung nachgefahren — `mode="auto"` fuer die moderne,
# `mode="legacy"` fuer die Handshake-Aera. Ein protokoll-aenderndes SDK-Update
# faellt damit laut auf, statt still zu driften.
MCP_MODERN_PROTOCOL_VERSION = "2026-07-28"
"""Die Revision, die eine frische Verbindung hier aushandelt (`server/discover`)."""

MCP_HANDSHAKE_PROTOCOL_VERSION = "2025-11-25"
"""Die Obergrenze, die ein Client der alten Aera ueber `initialize` noch bekommt."""

# `mask_error_details=True` keeps upstream/internal error text out of tool
# results (OBS-002); execution errors surface as `isError` tool-results while
# protocol errors stay JSON-RPC errors (OBS-001).
#
# `version=` ist nicht kosmetisch. Ohne das Argument traegt das `serverInfo`
# der Verbindung die Version von *FastMCP* — gemessen am 18.9.2026 meldete
# dieser Server `4.0.5` statt seiner eigenen `0.4.0`. Ein Client, der die
# Serverversion protokolliert oder gegen bekannte Fehler abgleicht, bekam
# damit die Nummer einer fremden Bibliothek. Die Nummer kommt aus den
# Paket-Metadaten, nicht aus einem Literal (`scripts/check_version_sync.py`
# verbietet Literale in `src/`).
mcp = FastMCP(
    "swiss-efv-mcp",
    version=__version__,
    website_url="https://github.com/malkreide/swiss-efv-mcp",
    lifespan=_lifespan,
    mask_error_details=True,
)

# Every tool is read-only: it only issues HTTP GETs against the EFV dumps and
# never writes. `openWorldHint` is True because responses depend on external
# upstream data (ARCH-009).
_READONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


# --- pure implementations (testable) ----------------------------------------


async def headline_impl(
    c: EFVClient,
    variable: str,
    household: str = "bund",
    model: str = "fs",
    year_from: int | None = None,
    year_to: int | None = None,
) -> HeadlineSeries:
    rows, prov = await c.load("headline")
    points: list[Point] = []
    for r in rows:
        if clean(r.get("variable")) != variable:
            continue
        if clean(r.get("hh")) != household:
            continue
        if clean(r.get("model")) != model:
            continue
        y = to_year(r.get("jahr"))
        if y is None:
            continue
        if year_from is not None and y < year_from:
            continue
        if year_to is not None and y > year_to:
            continue
        src = clean(r.get("source"))
        points.append(
            Point(
                year=y,
                value=to_float(r.get("value")),
                kind=src,
                is_projection=is_projection(src),
            )
        )
    points.sort(key=lambda p: p.year)
    note = None
    if not points:
        note = (
            f"No data matched variable={variable!r}, household={household!r}, "
            f"model={model!r}. Call fiscal_list_dimensions to see the valid values."
        )
    return HeadlineSeries(
        provenance=prov,
        variable=variable,
        household=household,
        model=model,
        points=points,
        note=note,
    )


async def budget_impl(
    c: EFVClient,
    topic: str = "Ausgaben nach Aufgabengebiet",
    year: int | None = None,
    level: int = 2,
    contains: str | None = None,
) -> BudgetBreakdown:
    rows, prov = await c.load("budget")
    years = sorted({to_year(r.get("year")) for r in rows if to_year(r.get("year")) is not None})
    target_year = year if year is not None else (years[-1] if years else 0)

    items: list[BreakdownItem] = []
    for r in rows:
        if clean(r.get("topic")) != topic:
            continue
        if to_year(r.get("year")) != target_year:
            continue
        lvl = to_year(r.get("category_level"))
        if lvl != level:
            continue
        path = clean(r.get("path")) or ""
        if contains and contains.lower() not in path.lower():
            continue
        items.append(
            BreakdownItem(
                label=clean(r.get("variable_name")) or path,
                level=lvl,
                value=to_float(r.get("value")),
                path=path,
            )
        )
    items.sort(key=lambda i: (i.value is None, -(i.value or 0)))
    note = None
    if topic.endswith("ab 2023)") or topic.endswith("bis 2022)"):
        note = "Accounting-model break: 2023 uses a new model; series has a seam at 2022/2023."
    elif not items:
        note = (
            f"No items at level={level} for topic={topic!r}, year={target_year}. "
            f"Try a different level (1 = total) or fiscal_list_dimensions for valid topics."
        )
    return BudgetBreakdown(
        provenance=prov, topic=topic, year=target_year, level=level, items=items, note=note
    )


async def institution_impl(
    c: EFVClient,
    departement: str | None = None,
    variable: str = "Personalausgaben",
    year_from: int | None = None,
    year_to: int | None = None,
) -> InstitutionSeries:
    rows, prov = await c.load("institutions")
    points: list[InstitutionPoint] = []
    for r in rows:
        if clean(r.get("variable_name")) != variable:
            continue
        dep = clean(r.get("departement"))
        if departement is not None and dep != departement:
            continue
        y = to_year(r.get("year"))
        if y is None:
            continue
        if year_from is not None and y < year_from:
            continue
        if year_to is not None and y > year_to:
            continue
        points.append(
            InstitutionPoint(
                departement=dep,
                verwaltungseinheit=clean(r.get("verwaltungseinheit")),
                variable=variable,
                year=y,
                value=to_float(r.get("value")),
            )
        )
    points.sort(key=lambda p: (p.year, p.verwaltungseinheit or ""))
    note = None
    if not points:
        note = (
            f"No data matched variable={variable!r}, departement={departement!r}. "
            f"Call fiscal_list_dimensions to see the valid departments and variables."
        )
    return InstitutionSeries(
        provenance=prov,
        filter_departement=departement,
        filter_variable=variable,
        points=points,
        note=note,
    )


async def dimensions_impl(c: EFVClient) -> Dimensions:
    h, hp = await c.load("headline")
    b, _ = await c.load("budget")
    i, _ = await c.load("institutions")

    def distinct(rows, col):
        return sorted({v for r in rows if (v := clean(r.get(col))) is not None})

    return Dimensions(
        provenance=hp,
        headline_variables=distinct(h, "variable"),
        households=distinct(h, "hh"),
        models=distinct(h, "model"),
        budget_topics=distinct(b, "topic"),
        institution_departments=distinct(i, "departement"),
        institution_variables=distinct(i, "variable_name"),
    )


def status_impl(c: EFVClient) -> StatusReport:
    ds = c.status()
    errors = [k for k, v in ds.items() if v.get("last_error")]
    healthy = not errors
    msg = (
        "All datasets reachable or cached."
        if healthy
        else f"Degraded: last error on {', '.join(errors)}. Retry in ~10 minutes."
    )
    return StatusReport(datasets=ds, healthy=healthy, message=msg)


# --- MCP tool wrappers ------------------------------------------------------


@mcp.tool(annotations=_READONLY)
async def fiscal_headline(
    variable: Annotated[str, Field(max_length=100)],
    household: Annotated[str, Field(max_length=40)] = "bund",
    model: Annotated[str, Field(max_length=20)] = "fs",
    year_from: Annotated[int | None, Field(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Field(ge=1900, le=2100)] = None,
) -> HeadlineSeries:
    """Headline fiscal time series: revenue, expenditure, balance and debt ratios
    from 1990 to the latest year the EFV publishes, actuals and forward-looking
    years alike. Read `is_projection` per point to tell them apart; not every
    household carries forward years.

    Use case: track how a federal aggregate evolved over time — e.g. "how did the
    Bund balance develop since the 2022 rate turnaround?". variable e.g. 'saldo',
    'einnahmen', 'ausgaben', 'bruttoschuldenquote'. household: bund|ktn|gdn|staat|sv.
    model: fs|gfs. Every point flags `is_projection`. Call fiscal_list_dimensions
    first to discover valid values; an empty result carries a `note` with guidance."""
    _log().debug("fiscal_headline", variable=variable, household=household, model=model)
    return await headline_impl(client, variable, household, model, year_from, year_to)


@mcp.tool(annotations=_READONLY)
async def fiscal_budget_breakdown(
    topic: Annotated[str, Field(max_length=120)] = "Ausgaben nach Aufgabengebiet",
    year: Annotated[int | None, Field(ge=1900, le=2100)] = None,
    level: Annotated[int, Field(ge=1, le=8)] = 2,
    contains: Annotated[str | None, Field(max_length=120)] = None,
) -> BudgetBreakdown:
    """Hierarchical federal-budget breakdown for one topic and year.

    Use case: see where the money goes — e.g. "which task areas absorbed the
    spending growth?". topic e.g. 'Ausgaben nach Aufgabengebiet', 'Ausgaben nach
    Art', 'Einnahmen'. level is the hierarchy depth (1 = total, 2 = first
    breakdown …); 'contains' filters the path substring for drill-down. An empty
    result carries a `note` suggesting a different level or topic."""
    _log().debug("fiscal_budget_breakdown", topic=topic, level=level)
    return await budget_impl(client, topic, year, level, contains)


@mcp.tool(annotations=_READONLY)
async def fiscal_by_institution(
    departement: Annotated[str | None, Field(max_length=120)] = None,
    variable: Annotated[str, Field(max_length=80)] = "Personalausgaben",
    year_from: Annotated[int | None, Field(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Field(ge=1900, le=2100)] = None,
) -> InstitutionSeries:
    """Federal spending by department / administrative unit since 2007.

    Use case: compare personnel, IT or external-services spending across
    departments — e.g. "IT spending of the Finanzdepartement since 2010?".
    variable one of: 'Personalausgaben', 'Informatik', 'Beratung und externe
    Dienstleistungen', 'Anzahl Vollzeitstellen'. An empty result carries a `note`
    with guidance."""
    _log().debug("fiscal_by_institution", departement=departement, variable=variable)
    return await institution_impl(client, departement, variable, year_from, year_to)


@mcp.tool(annotations=_READONLY)
async def fiscal_list_dimensions(ctx: Context | None = None) -> Dimensions:
    """List the valid dimension values across all datasets (variables,
    households, models, budget topics, departments).

    Use case: call this first to build correct parameters for the other tools —
    it turns free-text guesses into exact filter values. Loads all three dumps,
    so it may take a moment on a cold cache."""
    _log().debug("fiscal_list_dimensions", stage="loading all dumps")
    if ctx is not None:
        await ctx.report_progress(0, 3)
    result = await dimensions_impl(client)
    if ctx is not None:
        await ctx.report_progress(3, 3)
    return result


@mcp.tool(annotations=_READONLY)
async def fiscal_status() -> StatusReport:
    """Report cache freshness and upstream health per dataset.

    Use case: check whether the data is fresh, cached or degraded before trusting
    a figure — the health endpoint of this server. Never returns empty silently;
    used for graceful degradation."""
    _log().debug("fiscal_status")
    return status_impl(client)


@mcp.tool(annotations=_READONLY)
async def dump_status() -> StatusReport:
    """DEPRECATED — use `fiscal_status`. Kept as an alias for backward
    compatibility; will be removed in a future minor release.

    Reports cache freshness and upstream health per dataset (SEC-022: every tool
    now shares the `fiscal_` server-identity namespace)."""
    _log().debug("dump_status", note="deprecated alias of fiscal_status")
    return status_impl(client)
