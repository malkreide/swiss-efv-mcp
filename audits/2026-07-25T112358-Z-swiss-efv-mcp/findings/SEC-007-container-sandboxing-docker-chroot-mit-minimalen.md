## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

**Severity:** high
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SEC-007
**PDF-Reference:** Sec 4.5

### Observed Behavior
Check evaluated as **partial** after the hardening commit.

### Evidence
- Dockerfile:12 — useradd --uid 10001 non-root user (UID >= 10000)
- Dockerfile:14 — USER 10001 set before ENTRYPOINT
- Dockerfile:4-10 — multi-stage build (build stage + slim runtime)

### Gaps
- No readOnlyRootFilesystem (no k8s manifests / no runtime read-only enforcement)
- No capabilities drop (CapDrop ALL) and no seccomp profile referenced
- No Kubernetes SecurityContext (runAsNonRoot/allowPrivilegeEscalation:false) — no k8s/helm manifests in repo
- No container security scan (Trivy/Snyk) step in CI

### Remediation
### Schritt 1: Dockerfile-User anpassen

Wie im Pass-Pattern oben.

### Schritt 2: Kubernetes-SecurityContext setzen

Im Helm-Chart oder Deployment-Manifest.

### Schritt 3: Tests gegen Privileg-Eskalation

```python
def test_container_runs_as_non_root():
    result = subprocess.run(
        ["docker", "exec", CONTAINER_ID, "id", "-u"],
        capture_output=True, text=True,
    )
    assert int(result.stdout.strip()) >= 10000

def test_filesystem_read_only():
    result = subprocess.run(
        ["docker", "exec", CONTAINER_ID, "touch", "/etc/test"],
        capture_output=True, text=True,
    )
    assert "Read-only" in result.stderr or result.returncode != 0
```

### Schritt 4: CI-Check via Trivy / Snyk

```yaml
- name: Container security scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: malkreide/mcp-server:${{ github.sha }}
    severity: CRITICAL,HIGH
    exit-code: 1
```

### Effort Estimate
M (S < 1d · M 1-3d · L 1-2w · XL >2w)
