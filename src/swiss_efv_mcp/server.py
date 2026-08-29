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

from .client import EFVClient, clean, is_projection, to_float, to_year
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


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Own the shared HTTP client; close it cleanly on shutdown (SDK-001)."""
    try:
        yield
    finally:
        await client.aclose()


# MCP protocol baseline this server is built and audited against (ARCH-012).
# FastMCP negotiates the concrete version at the `initialize` handshake; a
# regression test asserts the negotiated version still equals this constant, so a
# protocol-changing SDK bump fails CI loudly instead of drifting silently. The
# `mcp` SDK floor in pyproject.toml (via fastmcp) is what supplies this version;
# Dependabot keeps it current.
MCP_PROTOCOL_VERSION = "2025-11-25"

# `mask_error_details=True` keeps upstream/internal error text out of tool
# results (OBS-002); execution errors surface as `isError` tool-results while
# protocol errors stay JSON-RPC errors (OBS-001).
mcp = FastMCP("swiss-efv-mcp", lifespan=_lifespan, mask_error_details=True)

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
    ctx: Context | None = None,
) -> HeadlineSeries:
    """Headline fiscal time series: revenue, expenditure, balance and debt ratios
    from 1990 to the latest year the EFV publishes (actuals, plus budget and
    forecast years wherever the source carries them — which households get
    forward years, and how far, is the source's call and has changed before).

    Use case: track how a federal aggregate evolved over time — e.g. "how did the
    Bund balance develop since the 2022 rate turnaround?". variable e.g. 'saldo',
    'einnahmen', 'ausgaben', 'bruttoschuldenquote'. household: bund|ktn|gdn|staat|sv.
    model: fs|gfs. Every point flags `is_projection`. Call fiscal_list_dimensions
    first to discover valid values; an empty result carries a `note` with guidance."""
    if ctx is not None:
        await ctx.debug(f"fiscal_headline variable={variable!r} household={household!r}")
    return await headline_impl(client, variable, household, model, year_from, year_to)


@mcp.tool(annotations=_READONLY)
async def fiscal_budget_breakdown(
    topic: Annotated[str, Field(max_length=120)] = "Ausgaben nach Aufgabengebiet",
    year: Annotated[int | None, Field(ge=1900, le=2100)] = None,
    level: Annotated[int, Field(ge=1, le=8)] = 2,
    contains: Annotated[str | None, Field(max_length=120)] = None,
    ctx: Context | None = None,
) -> BudgetBreakdown:
    """Hierarchical federal-budget breakdown for one topic and year.

    Use case: see where the money goes — e.g. "which task areas absorbed the
    spending growth?". topic e.g. 'Ausgaben nach Aufgabengebiet', 'Ausgaben nach
    Art', 'Einnahmen'. level is the hierarchy depth (1 = total, 2 = first
    breakdown …); 'contains' filters the path substring for drill-down. An empty
    result carries a `note` suggesting a different level or topic."""
    if ctx is not None:
        await ctx.debug(f"fiscal_budget_breakdown topic={topic!r} level={level}")
    return await budget_impl(client, topic, year, level, contains)


@mcp.tool(annotations=_READONLY)
async def fiscal_by_institution(
    departement: Annotated[str | None, Field(max_length=120)] = None,
    variable: Annotated[str, Field(max_length=80)] = "Personalausgaben",
    year_from: Annotated[int | None, Field(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Field(ge=1900, le=2100)] = None,
    ctx: Context | None = None,
) -> InstitutionSeries:
    """Federal spending by department / administrative unit since 2007.

    Use case: compare personnel, IT or external-services spending across
    departments — e.g. "IT spending of the Finanzdepartement since 2010?".
    variable one of: 'Personalausgaben', 'Informatik', 'Beratung und externe
    Dienstleistungen', 'Anzahl Vollzeitstellen'. An empty result carries a `note`
    with guidance."""
    if ctx is not None:
        await ctx.debug(f"fiscal_by_institution departement={departement!r} variable={variable!r}")
    return await institution_impl(client, departement, variable, year_from, year_to)


@mcp.tool(annotations=_READONLY)
async def fiscal_list_dimensions(ctx: Context | None = None) -> Dimensions:
    """List the valid dimension values across all datasets (variables,
    households, models, budget topics, departments).

    Use case: call this first to build correct parameters for the other tools —
    it turns free-text guesses into exact filter values. Loads all three dumps,
    so it may take a moment on a cold cache."""
    if ctx is not None:
        await ctx.debug("fiscal_list_dimensions: loading all dumps")
        await ctx.report_progress(0, 3)
    result = await dimensions_impl(client)
    if ctx is not None:
        await ctx.report_progress(3, 3)
    return result


@mcp.tool(annotations=_READONLY)
async def fiscal_status(ctx: Context | None = None) -> StatusReport:
    """Report cache freshness and upstream health per dataset.

    Use case: check whether the data is fresh, cached or degraded before trusting
    a figure — the health endpoint of this server. Never returns empty silently;
    used for graceful degradation."""
    if ctx is not None:
        await ctx.debug("fiscal_status")
    return status_impl(client)


@mcp.tool(annotations=_READONLY)
async def dump_status(ctx: Context | None = None) -> StatusReport:
    """DEPRECATED — use `fiscal_status`. Kept as an alias for backward
    compatibility; will be removed in a future minor release.

    Reports cache freshness and upstream health per dataset (SEC-022: every tool
    now shares the `fiscal_` server-identity namespace)."""
    if ctx is not None:
        await ctx.debug("dump_status (deprecated alias of fiscal_status)")
    return status_impl(client)
