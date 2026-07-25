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
network-layer egress control so the pod/VM can only reach the hosts above:

- **Kubernetes:** a `NetworkPolicy` with an egress rule to the two EFV hosts on 443.
- **Cloud:** a security-group / firewall egress rule, or an egress proxy allow-list.

## Updating the allow-list

Changing the set of reachable hosts is a code change (edit `ALLOWED_HOSTS`),
reviewed via pull request — never a runtime configuration toggle.
