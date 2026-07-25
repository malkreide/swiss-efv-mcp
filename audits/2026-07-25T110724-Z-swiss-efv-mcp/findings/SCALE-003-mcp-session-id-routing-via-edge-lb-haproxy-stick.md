## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior
Check evaluated as **fail** against the current code.

### Evidence
- grep for `stick|hdr(Mcp-Session|affinity|upstream-hash` across repo returned no matches
- No haproxy.cfg / nginx.conf / ingress*.yaml present anywhere in the repo (no deploy/ or helm/ directory)
- No edge-LB layer exists to read the Mcp-Session-Id header

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
