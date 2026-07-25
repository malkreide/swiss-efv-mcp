## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- client.py:41-74 — all three dataset URLs are hardcoded module constants (https:// on data.finance.admin.ch / efv.admin.ch); no user input ever builds a URL, so the primary SSRF vector is structurally absent
- client.py:122-123 — httpx.AsyncClient uses default TLS verification (never disabled) but follow_redirects=True
- SECURITY.md:22 & README.md:180-182 — documents fixed hardcoded egress, 'no SSRF surface'
- [remediated] client.py enforces https scheme + host allow-list before each request (improved); follow_redirects still on and no IP-literal blocklist — residual.

### Gaps
- No explicit HTTPS scheme validation before requests (no urlparse scheme check)
- No resolved-IP blocklist (169.254.169.254, private/loopback/link-local ranges never checked)
- No DNS pinning / getaddrinfo guard
- follow_redirects=True means an upstream 3xx could redirect the fetch to an internal/metadata IP with no post-resolution IP check — residual SSRF-via-redirect gap

### Remediation
Volles Pattern oben. Zusätzlich für Defense-in-Depth:

### Container-Level Egress-Filtering

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-server-egress
spec:
  podSelector:
    matchLabels:
      app: mcp-server
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
              - 169.254.0.0/16
              - 127.0.0.0/8
      ports:
        - protocol: TCP
          port: 443
```

### IMDSv2 statt IMDSv1 (AWS-spezifisch)

Falls auf AWS deployed: IMDSv2 mit Hop-Limit 1 erzwingen (verhindert SSRF auch bei Code-Bug).

```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxx \
  --http-tokens required \
  --http-put-response-hop-limit 1
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
