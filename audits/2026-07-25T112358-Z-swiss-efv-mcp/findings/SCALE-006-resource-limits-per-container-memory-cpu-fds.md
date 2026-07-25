## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

**Severity:** medium
**Status:** open (fail)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-006
**PDF-Reference:** Sec 5.3

### Observed Behavior
Check evaluated as **fail** after the hardening commit.

### Evidence
- No k8s/helm manifest, no docker-compose.yml, no railway.toml/render.yaml present in repo (ls of root) — nowhere to set memory/cpu limits
- Dockerfile has no `ulimit`/nofile configuration and no resource constraints
- grep of README for memory/cpu/resource limits found no documented limits (README.md:90-102 lists only TRANSPORT/HOST/PORT)

### Gaps
- No explicit memory limit, CPU limit, or FD limit defined or documented for the cloud deployment
- Relevant here because the in-memory dump cache can grow (multiple CSVs, up to ~5 MB each) — an unbounded pod could OOM the host
- No restart-policy / OOM-behavior documentation

### Remediation
Für Railway: in der Web-UI unter Project Settings → Resources die Limits setzen.

Für Docker-Compose-Production:

```yaml
services:
  mcp:
    image: malkreide/mcp-server:v0.1.0
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    ulimits:
      nofile:
        soft: 4096
        hard: 8192
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
