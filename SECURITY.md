# Security Policy & Posture

[🇩🇪 Deutsche Version](SECURITY.de.md)

`swiss-efv-mcp` is a **read-only**, **no-auth**, **public-open-data** MCP server.
This document summarises its security posture and how to report a vulnerability.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository, or contact the
maintainer listed in `README.md`. Do not file public issues for exploitable
vulnerabilities.

## Posture summary

All five tools only issue read requests against curated public EFV dump files on
two fixed hosts (`data.finance.admin.ch`, `efv.admin.ch`); there are no write,
send, or filesystem capabilities, and no personal data is processed.

This posture was verified against the portfolio MCP best-practice catalogue
(44 applicable checks) — see [`audits/`](audits/). The hardening below closes
the audit backlog; the run is reproducible from the stored `verification-results.json`.

| Area | Control |
|---|---|
| Egress | Code-layer allow-list: a module-level `frozenset` `ALLOWED_HOSTS` + `assert_host_allowed()` enforced before **every** request rejects non-HTTPS and any off-list host. URLs are hardcoded constants; no user input builds a URL. See [`docs/network-egress.md`](docs/network-egress.md). (SEC-021) |
| TLS | httpx certificate verification is on by default and never disabled in code |
| Auth / secrets | Unauthenticated public OGD — no API keys, tokens or secrets are stored or forwarded |
| Input | Pydantic v2 validation at all tool boundaries with explicit bounds (year `1900–2100`, hierarchy `level 1–8`, string `max_length`); tool arguments only filter cached rows, never build a URL (SEC-018) |
| Tools | Read-only: every tool is annotated `readOnlyHint: true`, `destructiveHint: false`; no dynamic or remote tool registration (ARCH-009) |
| Errors | `mask_error_details=True` plus client-side masking: execution errors surface as `isError` tool-results with a generic message; raw upstream/internal detail goes only to the structlog stderr log, never to the model (OBS-002) |
| Logging | Structured JSON logs to **stderr** via structlog; stdout is reserved for the JSON-RPC stream (OBS-003 / OBS-004) |
| Binding | `stdio` by default (no network surface). SSE binds to `HOST`, default `127.0.0.1` (loopback); `0.0.0.0` is an explicit opt-in for containers (SEC-016) |
| CORS | SSE sets default-deny CORS — browser origins must be listed explicitly via `EFV_MCP_CORS_ORIGINS`; only `Mcp-Session-Id` is exposed (SDK-004) |
| Container | Hardened non-root [`Dockerfile`](Dockerfile) (uid 10001) with a `HEALTHCHECK` (SEC-007 / SCALE-004) |

## Accepted risks (ADRs)

Two controls are deliberately deferred and documented as accepted-risk ADRs —
low risk for a single-instance, no-auth, read-only server reaching two fixed hosts:

- **DNS pinning** — [ADR 0001](docs/adr/0001-dns-pinning.md) (SEC-005): no
  user-controlled destination + the egress allow-list neutralise the
  DNS-rebinding precondition.
- **Stateful load balancing** — [ADR 0002](docs/adr/0002-scaling-and-deployment.md)
  (SCALE-002 / SCALE-003): operated as a single instance; sticky sessions /
  shared session store deferred with explicit re-evaluation triggers.

## Accepted risks (portfolio-level controls)

The following are handled at the MCP gateway / host layer rather than inside
this single server. Residual risk here is low because the server is read-only,
unauthenticated, and reaches only two trusted public-data hosts.

- **Session crypto-binding** — not applicable: there is no user identity to bind,
  as the server exposes public data with no authentication.
- **Cross-server tool-poisoning detection** — a gateway/host responsibility. This
  server's tool definitions are version-controlled, authored in-repo, and
  reviewed via PR; there is no dynamic or remote tool registration.
- **Tool namespace & hash pinning (SEC-022)** — every tool shares the `fiscal_`
  server-identity prefix, and the server is published under the MCP Registry name
  `io.github.malkreide/swiss-efv-mcp`. Detecting a *tool-definition change across
  sessions* ("rug pull") is a gateway/host responsibility — a single server
  cannot attest its own immutability — so tool-hash pinning is enforced at that
  layer, not here.
- **Network binding for hosted deployments** — the SSE transport defaults to
  `127.0.0.1` (loopback). Binding to `0.0.0.0` is an explicit opt-in for
  container deployments; front it with a reverse proxy / gateway that enforces
  TLS and access control.
- **Browser User-Agent** — the EFV endpoints reject the default httpx/curl UA
  with HTTP 403, so a static browser UA is injected. It carries no user data and
  is not a tracking or authentication token.

## Re-evaluation triggers

Revisit these acceptances if the server ever:

- gains **write** capability or starts processing **PII**, or
- adds an **authentication** model (then implement bound, TTL'd,
  server-side-invalidated session IDs and re-audit before merge), or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then enable the gateway's tool
  allow-listing and tool-poisoning detection).
