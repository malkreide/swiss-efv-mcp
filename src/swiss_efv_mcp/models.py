"""Pydantic v2 response envelopes.

Every tool returns an envelope carrying ``source`` (attribution) and
``provenance`` so attribution can never be dropped — the README is not
forwarded to the model, the response is.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .client import ATTRIBUTION

Provenance = Literal["dump", "cached"]


class Envelope(BaseModel):
    source: str = Field(default=ATTRIBUTION)
    provenance: Provenance = Field(description="dump = freshly fetched CSV, cached = in-memory")


class Point(BaseModel):
    year: int
    value: float | None
    kind: str | None = Field(
        default=None,
        description=(
            "raw EFV source label, passed through verbatim — e.g. 'Rechnung', "
            "'Prognosen'. The source picks its own wording and has switched "
            "language before (English until 2026-08-27), so branch on "
            "`is_projection` rather than on this string."
        ),
    )
    is_projection: bool | None = Field(
        default=None,
        description="True if the year is forward-looking (budget/plan/forecast), False if settled",
    )


class HeadlineSeries(Envelope):
    variable: str
    household: str = Field(description="hh: bund | ktn | gdn | staat | sv | bund_ktn_gdn")
    model: str = Field(description="fs (Finanzstatistik) | gfs (GFS-Modell)")
    unit: str = "CHF mio / % (variable-dependent)"
    points: list[Point]
    note: str | None = Field(
        default=None,
        description="guidance when the result is empty or has a caveat (ARCH-003)",
    )


class BreakdownItem(BaseModel):
    label: str
    level: int
    value: float | None
    path: str


class BudgetBreakdown(Envelope):
    topic: str
    year: int
    level: int
    items: list[BreakdownItem]
    note: str | None = None


class InstitutionPoint(BaseModel):
    departement: str | None
    verwaltungseinheit: str | None
    variable: str
    year: int
    value: float | None


class InstitutionSeries(Envelope):
    filter_departement: str | None
    filter_variable: str | None
    points: list[InstitutionPoint]
    note: str | None = Field(
        default=None,
        description="guidance when the result is empty or has a caveat (ARCH-003)",
    )


class Dimensions(Envelope):
    headline_variables: list[str]
    households: list[str]
    models: list[str]
    budget_topics: list[str]
    institution_departments: list[str]
    institution_variables: list[str]


class StatusReport(BaseModel):
    source: str = Field(default=ATTRIBUTION)
    datasets: dict
    healthy: bool
    message: str
