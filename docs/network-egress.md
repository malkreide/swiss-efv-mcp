# Network egress (SEC-021)

`swiss-efv-mcp` reaches exactly **two** external hosts — the EFV FS/GFS dump
files. No tool argument ever contributes to a URL; the dataset URLs are module
constants in `src/swiss_efv_mcp/client.py`.

## Code-layer allow-list

`client.py` defines an immutable allow-list and enforces it before every
outbound request:

```python
ALLOWED_HOSTS = frozenset({
    "www.data.finance.admin.ch",
    "www.efv.admin.ch",
})

def assert_host_allowed(url: str) -> None:
    # rejects non-https and any host outside ALLOWED_HOSTS
    ...
```

`_fetch_with_retry()` calls `assert_host_allowed()` first, so a bug or an
injected URL cannot cause a request to any other host. The allow-list is a
module-level `frozenset` — it is not configurable or mutable at runtime.

| Host | Scheme | Purpose |
|---|---|---|
| `www.data.finance.admin.ch` | https | FS/GFS headline dump (`fs_dashboard/main_extern.csv`) |
| `www.efv.admin.ch` | https | Budget & institution dumps (DAM CSV paths) |

## Network-layer control (deployment)

When deploying the SSE container, pair the code-layer allow-list with a
network-layer egress control so the pod/VM can only reach the hosts above. This
is also the recommended mitigation for **DNS rebinding (SEC-005, [ADR 0001](adr/0001-dns-pinning.md))**:
enforcing the destination at the network edge removes the need for per-request
DNS pinning in application code.

- **Kubernetes:** a default-deny egress `NetworkPolicy`, plus an allow rule to
  the two EFV hosts on TCP 443 (resolve via an egress gateway / DNS policy that
  only permits `*.admin.ch`, or pin the resolved CIDRs).

  ```yaml
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  metadata: { name: efv-mcp-egress }
  spec:
    podSelector: { matchLabels: { app: swiss-efv-mcp } }
    policyTypes: [Egress]
    egress:
      - to: []                       # DNS
        ports: [{ protocol: UDP, port: 53 }]
      - to: []                       # HTTPS to admin.ch (front with an egress proxy allow-list)
        ports: [{ protocol: TCP, port: 443 }]
  ```

- **Cloud:** a security-group / firewall egress rule limited to TCP 443 toward
  the EFV hosts, or an **egress proxy** whose allow-list is exactly
  `www.data.finance.admin.ch` and `www.efv.admin.ch`. An egress proxy is the
  strongest control: it re-resolves and re-checks the host on every connection,
  which is what a code-level DNS pin would do — but centrally and audibly.

## Updating the allow-list

Changing the set of reachable hosts is a code change (edit `ALLOWED_HOSTS`),
reviewed via pull request — never a runtime configuration toggle.
