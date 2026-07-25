## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** in-remediation (partial) — accepted-risk / documented deferral
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4

### Observed Behavior
Check evaluated as **partial**. This is an accepted risk documented in an
ADR / `docs/roadmap.md`; the mitigation path is prescribed, not silently ignored.

### Evidence
- client.py:42,58,64,70 — hostnames are fixed trusted EFV constants, not user-controlled, so an attacker cannot introduce a rebinding domain
- client.py:122-123 — httpx default client, no custom transport, no DNS pinning; follow_redirects=True
- [remediated] Accepted-risk documented in docs/adr/0001-dns-pinning.md; no user-controlled host + egress allow-list neutralise the rebinding precondition.
- [v0.3.0-bundle] Accepted-risk ADR 0001; docs/network-egress.md now prescribes the network-layer mitigation (default-deny egress NetworkPolicy / egress-proxy allow-list) that supersedes code DNS-pinning.

### Gaps
- No DNS-Pinning: no getaddrinfo/ipaddress single-resolution logic (grep confirms neither symbol present in src/)
- httpx default performs implicit resolution with no pinned-IP reuse (TOCTOU window exists in principle)
- No SNI/Host-header preservation logic because no pinning implemented
- follow_redirects=True could follow a redirect to a rebound host without re-validation

### Remediation
### Schritt 1: HTTP-Client mit Custom Transport

```python
import httpx
import socket
import ipaddress

class PinnedTransport(httpx.AsyncHTTPTransport):
    """HTTPX Transport mit DNS-Pinning."""

    async def handle_async_request(self, request):
        url = request.url
        if url.scheme != "https":
            raise httpx.RequestError("Only HTTPS allowed")

        # Resolve einmalig
        loop = asyncio.get_event_loop()
        addrinfo = await loop.getaddrinfo(
            url.host, url.port, type=socket.SOCK_STREAM
        )
        resolved_ip = addrinfo[0][4][0]

        # Range-Check
        ip = ipaddress.ip_address(resolved_ip)
        for blocked in BLOCKED_NETWORKS:
            if ip in blocked:
                raise httpx.RequestError(f"Blocked IP: {ip}")

        # URL mit gepinnter IP, aber Host-Header bleibt
        pinned_url = httpx.URL(str(url).replace(url.host, resolved_ip, 1))
        new_request = httpx.Request(
            method=request.method,
            url=pinned_url,
            headers=httpx.Headers(request.headers),
            content=request.content,
            extensions=request.extensions,
        )
        new_request.headers["Host"] = url.host
        # SNI bleibt durch URL-Hostname (httpx interner default)
        return await super().handle_async_request(new_request)


# Verwendung
async with httpx.AsyncClient(transport=PinnedTransport()) as client:
    response = await client.get("https://api.external.com/data")
```

### Schritt 2: Alternative — Egress-Proxy

Wenn Custom-Transport zu komplex: Stripe Smokescreen als Sidecar erledigt DNS-Pinning automatisch.

```yaml
# docker-compose.yml
services:
  smokescreen:
    image: stripe/smokescreen:latest
    command: ["--listen-ip", "127.0.0.1", "--listen-port", "4750"]

  mcp-server:
    image: malkreide/mcp-server
    environment:
      HTTPS_PROXY: http://smokescreen:4750
```

```python
# Im Code: einfach Proxy nutzen
async with httpx.AsyncClient(proxy="http://localhost:4750") as client:
    return await client.get(url)
```

### Schritt 3: Tests

Wie im Mock-Beispiel oben. Plus Integration-Test, der nachweist dass die SSRF-Test-Suite (SEC-004 Modus 3) auch mit Rebinding-Versuchen besteht.

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
