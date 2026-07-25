## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** in-remediation (partial) — accepted-risk / documented deferral
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **partial**. This is an accepted risk documented in an
ADR / `docs/roadmap.md`; the mitigation path is prescribed, not silently ignored.

### Evidence
- grep for `stick|hdr(Mcp-Session|affinity|upstream-hash` across repo returned no matches
- No haproxy.cfg / nginx.conf / ingress*.yaml present anywhere in the repo (no deploy/ or helm/ directory)
- No edge-LB layer exists to read the Mcp-Session-Id header
- [remediated] Covered by docs/adr/0002 — Mcp-Session-Id edge routing deferred for the single-instance deployment; re-evaluation triggers documented.
- [v0.3.0-bundle] ADR 0002 now includes a concrete Mcp-Session-Id sticky-session example (nginx/Ingress/Traefik) for the multi-replica case; single-instance stays stateless-per-request.

### Gaps
- No Mcp-Session-Id header-based routing at any LB layer (complements the SCALE-002 gap)
- If deployed with >1 replica behind a default LB, sessions would round-robin without affinity and collapse

### Remediation
Für K8s-Ingress (NGINX):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-ingress
  annotations:
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "mcp-route"
    nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"
spec:
  rules:
  - host: mcp.example.ch
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mcp-server
            port:
              number: 8080
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
