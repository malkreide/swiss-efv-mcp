## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- README.md:208-220 ‘Project Phase’ explicitly declares Phase 1 (read-only) with a status table (Phase 1 ✅ current, Phase 2 detail cubes planned, Phase 3 none planned) and states a re-audit is required before any write-capable tool.
- Phase matches tool annotations: all five tools are read-only (README.md:114-116, 178-179 ‘Read-only by design’; server.py tools only call HTTP GET via client.load()); no destructive/write tools exist.
- README.de.md:212 ‘Projektphase’ mirrors the phase declaration bilingually.
- CHANGELOG references Phase-2 deferral of detail cubes (CHANGELOG.md:63-64).

### Gaps
- No dedicated `docs/roadmap.md` file (docs/ directory does not exist); the roadmap lives only as an inline README table — the check's Modus 3 wants a roadmap file with phase-specific tasks.
- Phase-1 prerequisite artifacts named in the check (ISDS-Klassifikation, DSG-Verarbeitungsverzeichnis, recorded audit-run) are not present/linked — though several are arguably N/A for a private non-governmental project over public data.
- Core phase discipline (explicit declaration + read-only tool match) is satisfied; the formal roadmap-file and prerequisite-doc scaffolding is missing.

### Remediation
### Schritt 1: Phase-Audit pro Server

Pro Server im Portfolio:

| Frage | Antwort |
|---|---|
| Hat der Server destruktive Tools? | ja → mindestens Phase 3 |
| Hat der Server Semantic Layer / Federation? | ja → mindestens Phase 2 |
| Sonst | Phase 1 |

### Schritt 2: Phase-Sektion ins README

Mit Status-Tabelle wie im Pass-Pattern Modus 1.

### Schritt 3: Roadmap erstellen

Mit Phase-Voraussetzungen als Tasks. Falls aktueller Server in Phase 2 oder 3 ist und Phase-1-Voraussetzungen fehlen: Findings im Audit-Tracker dokumentieren, retroaktiv schliessen.

### Schritt 4: Phase-Gate als Notion-Workflow

In Notion-Audit-Tracker-Schema (`a2736a65-...`) ein Feld «Phase» (Single-Select: 1, 2, 3) mit klaren Übergangs-Anforderungen.

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
