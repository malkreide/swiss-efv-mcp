## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- server.py:191-248 — FastMCP derives an input schema from the typed signatures, so type-level validation exists (e.g. year_from: int | None is enforced as int; a non-int LLM value is rejected at the boundary)
- server.py:191-233 — tool args (variable: str, household: str, level: int, contains: str|None) only filter already-cached in-memory rows; they never build a URL, reach a subprocess, or hit SQL (harmless sink)
- models.py:19-88 — Pydantic v2 envelopes exist but are response models, not input-constraint schemas

### Gaps
- No numeric ge/le constraints on int args (level, year_from, year_to) — LLM can pass arbitrary/negative/huge ints
- No str min_length/max_length or whitelist pattern on string args (variable, household, model, topic, contains, departement)
- No Pydantic strict=True and no extra='forbid' on any input model
- SECURITY.md:25 overstates this as full 'Pydantic v2 validation at all tool boundaries' — only type validation is present, not constraint validation

### Remediation
### Schritt 1: Schema pro Tool extrahieren

```diff
+ from typing import Annotated
+ from pydantic import BaseModel, Field, StringConstraints
+
+ class SearchArgs(BaseModel):
+     model_config = {"strict": True, "extra": "forbid"}
+     query: Annotated[str, StringConstraints(min_length=2, max_length=200)]
+     limit: Annotated[int, Field(ge=1, le=100)] = 10

  @mcp.tool()
- async def search(query: str, limit: int = 10) -> dict:
+ async def search(args: SearchArgs, ctx: Context) -> dict:
-     return await db.search(query, limit=limit)
+     return await db.search(args.query, limit=args.limit)
```

### Schritt 2: ValidationError sauber behandeln

```python
from pydantic import ValidationError

@mcp.tool()
async def search(args: SearchArgs, ctx: Context) -> dict:
    try:
        # Pydantic validiert beim Parsing automatisch — kein Aufruf nötig
        # Falls manuell aus dict gebaut: SearchArgs.model_validate(raw_dict)
        return await db.search(args.query, limit=args.limit)
    except ValidationError as e:
        # Wird normal nicht erreicht (FastMCP fängt das ab),
        # aber Defense-in-Depth:
        return {
            "isError": True,
            "content": [TextContent(
                type="text",
                text=f"Invalid arguments: {e.errors()[0]['msg']}"
            )],
        }
```

### Schritt 3: Tests gegen Edge-Cases

```python
@pytest.mark.parametrize("invalid_args,expected_error", [
    ({"query": "a", "limit": 10}, "min_length"),       # zu kurz
    ({"query": "x"*500, "limit": 10}, "max_length"),   # zu lang
    ({"query": "test", "limit": 0}, "greater_than_or_equal"),
    ({"query": "test", "limit": 99999}, "less_than_or_equal"),
    ({"query": "test", "limit": 10, "evil": "field"}, "extra_forbidden"),
])
async def test_search_rejects_invalid(invalid_args, expected_error):
    with pytest.raises(ValidationError) as exc:
        SearchArgs.model_validate(invalid_args)
    assert any(expected_error in err["type"] for err in exc.value.errors())
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
