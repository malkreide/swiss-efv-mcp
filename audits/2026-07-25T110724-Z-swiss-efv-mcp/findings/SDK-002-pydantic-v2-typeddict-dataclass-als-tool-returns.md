## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- pyproject.toml:29 pins `pydantic>=2.7` (Pydantic v2).
- models.py:19-21 defines an `Envelope(BaseModel)` with `source` (default=ATTRIBUTION) + `provenance: Provenance` where `Provenance = Literal["dump","cached"]` (models.py:16) — consistent envelope, Literal enum, no mutable defaults (uses Field(default=...)).
- All five response models (HeadlineSeries, BudgetBreakdown, InstitutionSeries, Dimensions extend Envelope; StatusReport carries source) are proper Pydantic v2 BaseModels with typed fields.
- The *_impl functions have correct model return annotations (e.g. server.py:37-44 `-> HeadlineSeries`).

### Gaps
- The @mcp.tool wrappers are annotated `-> dict` and return `.model_dump()` (server.py:197/204, 213/218, 227/233, 237/241, 245/248), so FastMCP receives a plain dict and does NOT expose the rich Pydantic output schema in tools/list — the model-level schema benefit is discarded at the tool boundary.
- No `count` / `match_type` fields on search-style envelopes (minor; envelope has source+provenance+results-equivalent lists).
- Remediation: annotate tools to return the Pydantic model directly (e.g. `-> HeadlineSeries`) and return the model instance instead of `.model_dump()`.

### Remediation
```diff
+ from pydantic import BaseModel, Field
+ from typing import Literal
+
+ class SearchResponse(BaseModel):
+     source: str = Field(default="DataSource Name — CC BY 4.0")
+     provenance: Literal["live_api", "cached", "weekly_dump"]
+     results: list[dict]
+     count: int

  @mcp.tool()
- async def search(query: str):
-     results = await api.search(query)
-     return {"results": results, "count": len(results)}
+ async def search(query: str, ctx) -> SearchResponse:
+     results = await api.search(query)
+     return SearchResponse(
+         provenance="live_api",
+         results=results,
+         count=len(results),
+     )
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
