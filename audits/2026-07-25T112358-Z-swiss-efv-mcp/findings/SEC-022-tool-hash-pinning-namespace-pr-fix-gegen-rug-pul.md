## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-022
**PDF-Reference:** Anhang B4

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- server.py:190-241 — 4 of 5 tools carry a topic prefix (fiscal_headline, fiscal_budget_breakdown, fiscal_by_institution, fiscal_list_dimensions), reducing collision risk
- SECURITY.md:38-41 — tool definitions are version-controlled, authored in-repo, PR-reviewed, with no dynamic/remote registration (partial rug-pull mitigation)
- server.py:245 — dump_status has no prefix at all; no server-identity namespace (e.g. swiss_efv__) is used

### Gaps
- No server-identity namespace prefix: 'fiscal_' is a topic prefix, not a <server>__ identity prefix, and is inconsistent (dump_status unprefixed) — cross-server shadowing not structurally prevented
- No tool-definition hash snapshot generated at release: publish.yml has no sha256/tool-hashes.json step (grep of CHANGELOG/server.json finds no hash/namespace mention)
- No CHANGELOG discipline for tool-definition changes / re-approval hints

### Remediation
### Schritt 1: Namespace-Audit

Server-Identity festlegen — typisch der Repo-Name als snake_case-Präfix:

| Repo | Namespace |
|---|---|
| `zh-education-mcp` | `zh_education` |
| `zurich-opendata-mcp` | `zurich_opendata` |
| `parlament-mcp` | `parlament_ch` |

### Schritt 2: Tool-Renaming

```diff
- @mcp.tool()
- async def search(query: str): ...
+ @mcp.tool(name="zh_education__search")
+ async def search(query: str): ...
```

Bei Renaming: Major-Version-Bump, da Tool-Namen Breaking-Changes sind.

### Schritt 3: Hash-Snapshot-Workflow

CI-Step wie im Pass-Pattern Modus 2. `tool-hashes.json` als Artefakt im Release.

### Schritt 4: Bei Update-Disziplin (Synergie zu ARCH-012)

CHANGELOG-Template um «Tool Definition Changes»-Sektion erweitern:

```markdown

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
