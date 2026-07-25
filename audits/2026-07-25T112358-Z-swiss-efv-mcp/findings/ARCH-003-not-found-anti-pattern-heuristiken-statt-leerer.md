## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- src/swiss_efv_mcp/server.py:71-73,148-153 — empty searches never return a bare [] or 'No results' string; they return a structured Pydantic envelope (HeadlineSeries/InstitutionSeries) carrying source+provenance even when points is empty
- src/swiss_efv_mcp/server.py:237-241 + 156-172 — a dedicated fiscal_list_dimensions tool exists so the model can discover valid dimension values instead of guessing after an empty hit
- src/swiss_efv_mcp/server.py:175-184,244-248 — dump_status is explicitly designed to 'never return empty silently' and reports degradation with an actionable retry hint

### Gaps
- No match_type field (exact/fuzzy/none) on any search response — server.py:71-73 (headline) and 148-153 (institution) return empty points with no match_type marker
- No fuzzy fallback or suggestion mechanism and no actionable per-tool 'note' on an empty result set; an empty fiscal_headline/fiscal_by_institution call yields empty points with no pointer back to fiscal_list_dimensions
- budget_impl only sets a 'note' for the accounting-model seam (server.py:108-110), not for the zero-results case

### Remediation
```diff
  @mcp.tool()
  async def find_school(name: str) -> list:
      results = await db.find(name)
-     if not results:
-         return []
+     if not results:
+         fuzzy = await db.find_fuzzy(name, threshold=0.7)
+         suggestions = await db.popular_school_names_starting_with(name[:3])
+         return {
+             "results": fuzzy[:5],
+             "match_type": "fuzzy" if fuzzy else "none",
+             "note": (
+                 f"Keine exakten Treffer für '{name}'. "
+                 f"{'Ähnliche Schulen aufgeführt.' if fuzzy else ''} "
+                 f"Häufige Schulnamen: {', '.join(suggestions[:5])}"
+             ),
+         }
      return {"results": results, "match_type": "exact"}
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
