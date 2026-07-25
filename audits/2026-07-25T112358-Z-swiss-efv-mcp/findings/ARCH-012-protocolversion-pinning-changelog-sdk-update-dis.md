## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- CHANGELOG.md:1-6 — present and in Keep-a-Changelog format with SemVer reference; [Unreleased] and [0.1.0] sections maintained
- .github/dependabot.yml:3-11 — monthly pip updates active (comment notes it keeps the mcp/fastmcp SDK current), satisfying the SDK-update-discipline criterion
- README.md:222-228 — a dedicated 'MCP Protocol Version' section exists and notes protocol-relevant bumps go in CHANGELOG.md

### Gaps
- protocolVersion is NOT explicitly pinned in code — grep for protocolVersion|protocol_version|PROTOCOL_VERSION in src/ returns nothing; README.md:224-228 states the version is 'negotiated at the initialize handshake by FastMCP' rather than pinned, which is exactly the Fail-Pattern (SDK default, can shift on update)
- No documented Breaking-Change / compatibility-window policy tied to a specific spec version; CHANGELOG has no spec-version-bump entries yet (only 0.1.0)

### Remediation
### Schritt 1: protocolVersion pinnen

```diff
+ from importlib.metadata import version

  mcp = FastMCP(
      name="zh-education-mcp",
+     protocol_version="2025-06-18",
  )
```

### Schritt 2: CHANGELOG initialisieren

Wenn nicht vorhanden, mit Template starten und retroaktiv Major-Versionen dokumentieren (mindestens letzte 3).

### Schritt 3: Dependabot konfigurieren

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
```

### Schritt 4: Quartalsweise Spec-Review

Im Audit-Tracker (Notion) oder GitHub Issues ein recurring Reminder für quartalsweise Spec-Velocity-Review:

- Was hat sich an der MCP-Spec geändert seit letztem Release?
- Welche Server müssen ihre `protocolVersion` aktualisieren?
- Gibt es Compliance-relevante Spec-Änderungen?

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
