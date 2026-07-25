## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

**Severity:** medium
**Status:** in-remediation (partial)
**Server:** swiss-efv-mcp
**Check-Reference:** SCALE-004
**PDF-Reference:** Sec 5.3

### Observed Behavior
Check evaluated as **partial** against the current code.

### Evidence
- Dockerfile:4 and :10 — two FROM statements (multi-stage build); both use python:3.12-slim base
- Dockerfile:4 — first stage named `AS build`; Dockerfile:10 — second (runtime) stage is NOT named
- Dockerfile:11-14 — non-root user created (uid 10001) and `USER 10001` set
- Dockerfile:8 — `pip install --no-cache-dir --prefix=/install`; Dockerfile:21 EXPOSE 8000
- No HEALTHCHECK directive anywhere in the Dockerfile

### Gaps
- No HEALTHCHECK directive — LB/orchestrator cannot verify container readiness
- Runtime stage is unnamed (`AS runtime` missing) — minor; check calls for named stages
- Final image size (<200 MB) not verified but plausible (slim base + 3 pure-Python deps)

### Remediation
```diff
- FROM python:3.11
- WORKDIR /app
- COPY . .
- RUN pip install -e .
- CMD ["python", "-m", "server"]
+ FROM python:3.11-slim AS builder
+ WORKDIR /build
+ COPY pyproject.toml .
+ COPY src/ ./src/
+ RUN pip install --no-cache-dir --user -e .
+
+ FROM python:3.11-slim AS runtime
+ COPY --from=builder /root/.local /root/.local
+ COPY src/ /app/src/
+ WORKDIR /app
+ ENV PATH=/root/.local/bin:$PATH PYTHONUNBUFFERED=1
+ USER nobody
+ HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
+ CMD ["python", "-m", "server"]
```

### Effort Estimate
S (S < 1d · M 1-3d · L 1-2w · XL >2w)
