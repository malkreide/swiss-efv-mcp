## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- client.py:41-74 — egress is de-facto fixed to three hardcoded https constants on two EFV hosts; no user input can introduce a new host (stronger than a mutable allow-list in that dimension)
- README.md:180-182 & SECURITY.md:22 — the two allowed EFV hosts and fixed-egress posture are documented
- client.py:122-123 — single httpx client; TLS verification on

### Gaps
- No explicit code-layer allow-list: no frozenset ALLOWED_HOSTS and no assert_host_allowed() pre-request guard (grep finds neither)
- No network-layer egress control (no k8s NetworkPolicy, no docs/network-egress.md, no security-group rules)
- follow_redirects=True (client.py:123) permits a redirect to leave the fixed EFV hosts with no host re-check
- No documented update procedure for changing the egress set

### Remediation
### Schritt 1: Allow-List-Inventar

Pro Server alle ausgehenden HTTP-Hosts identifizieren:

```bash
grep -rE 'https://[a-z0-9.-]+' src/ | \
  sed -E 's/.*https:\/\/([a-z0-9.-]+).*/\1/' | sort -u
```

Resultat: minimale Allow-Liste.

### Schritt 2: Code-Layer einbauen

Wie Pass-Pattern Modus 1.

### Schritt 3: Network-Layer einbauen

Bei Kubernetes: NetworkPolicy wie oben. Bei AWS: Security Group mit egress-Rules. Bei Cloudflare WARP: Zero-Trust-Policy.

### Schritt 4: Tests gegen Regression

```python
async def test_egress_blocked_to_non_allowlisted_host():
    with pytest.raises(PermissionError, match="not in allow-list"):
        await fetch_external_data("https://evil.example.com/", mock_ctx())


async def test_egress_allowed_to_allowlisted_host():
    # Mock-Response, kein echter Network-Call
    with respx.mock:
        respx.get("https://opendata.swiss/api/...").respond(200, json={"ok": True})
        result = await fetch_external_data("https://opendata.swiss/api/...", mock_ctx())
        assert result["ok"]
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
