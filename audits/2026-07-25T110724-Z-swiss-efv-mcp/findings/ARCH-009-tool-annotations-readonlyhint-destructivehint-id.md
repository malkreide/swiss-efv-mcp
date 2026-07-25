## Finding: ARCH-009 — Tool Annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-009
**PDF-Reference:** Anhang A5

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- src/swiss_efv_mcp/server.py:190,207,221,236,244 — all 5 tools use bare @mcp.tool() with no annotations argument; grep for readOnlyHint|destructiveHint|idempotentHint|openWorldHint in src/ returns nothing
- README.md:114-115 — read-only nature is stated in prose ('All tools are read-only by design') but is not encoded as machine-readable ToolAnnotations the host can consume

### Gaps
- No tool sets explicit annotations, so hosts must treat every call pessimistically (confirmation fatigue); the 'all tools have explicit annotations' criterion fails outright
- Remediation: add annotations={'readOnlyHint': True, 'idempotentHint': True, 'openWorldHint': True} (tools do reach external EFV hosts) to all 5 read-only tools, and add an annotations overview table to the README

### Remediation
### Schritt 1: Annotations-Inventar

Pro Tool eine Tabelle mit den vier Hints. Wenn unsicher: per Default konservativ (alles `false`/weggelassen impliziert «kann gefährlich sein»).

### Schritt 2: Decorator-Helper

```python
from typing import Literal

def read_only_tool(*args, **kwargs):
    """Shortcut für read-only Tools mit konsistenten Annotations."""
    annotations = kwargs.pop("annotations", {})
    annotations.update({
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    })
    kwargs["annotations"] = annotations
    return mcp.tool(*args, **kwargs)


@read_only_tool()
async def search_motions(args, ctx):
    ...
```

### Schritt 3: CI-Test gegen Drift

```python
def test_destructive_tools_have_destructive_hint():
    """Tools mit delete/create/update im Namen müssen destructiveHint setzen."""
    suspicious_prefixes = ("delete_", "create_", "update_", "remove_")
    for tool_name, tool in mcp.tools.items():
        if any(tool_name.startswith(p) for p in suspicious_prefixes):
            annotations = tool.annotations or {}
            assert annotations.get("readOnlyHint") is not True, (
                f"{tool_name} suggests write but is marked readOnlyHint"
            )
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
