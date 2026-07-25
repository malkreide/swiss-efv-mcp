## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-002
**PDF-Reference:** Sec 2.2

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- src/swiss_efv_mcp/server.py:198-247 — every tool docstring is a multi-line description well above the 100-char median threshold and includes parameter guidance and enum hints
- src/swiss_efv_mcp/server.py:198-201 — fiscal_headline description names valid values ('saldo','einnahmen',...) and points to fiscal_list_dimensions (implicit use-case guidance)

### Gaps
- No structured XML-style tags present anywhere: grep for <use_case>|<important_notes>|<example> in src/ returns nothing, so the ≥80%-use_case-tag criterion is unmet
- Descriptions lack explicit <important_notes> for caveats (e.g. the 2022/2023 accounting-model seam is only surfaced at runtime via a 'note' field, not in the tool description)

### Remediation
```diff
  @mcp.tool(
      name="searchEducationStats",
-     description="Search education statistics."
+     description=(
+         "Sucht in den städtischen Bildungsstatistiken nach Kennzahlen "
+         "(Klassengrösse, Lehrer-Schüler-Verhältnis, Anteil DaZ, etc.).\n\n"
+         "<use_case>Politische / journalistische Recherche, "
+         "Schulamts-interne Reportings, Pädagogik-Analysen.</use_case>\n\n"
+         "<important_notes>Daten werden quartalsweise aktualisiert. "
+         "Personendaten sind nicht abrufbar — nur aggregierte "
+         "Kennzahlen.</important_notes>"
+     ),
  )
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
