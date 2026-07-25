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

| Area | Control |
|---|---|
| Egress | Dataset URLs are hardcoded constants on two EFV hosts; no user-supplied URLs enter a request, so there is no SSRF surface |
| TLS | httpx certificate verification is on by default and never disabled in code |
| Auth / secrets | Unauthenticated public OGD — no API keys, tokens or secrets are stored or forwarded |
| Input | Pydantic v2 validation at all tool boundaries; tool arguments only filter cached rows, never build a URL |
| Tools | Read-only by design (HTTP GET only); no dynamic or remote tool registration |
| Errors | Upstream failures are surfaced via `dump_status`, never silently swallowed or returned as an empty-but-complete-looking result |
| Stdout | Reserved for the JSON-RPC stream; the server emits no stray stdout logging |
| Binding | `stdio` by default (no network surface). SSE binds to `HOST`, default `127.0.0.1` (loopback); `0.0.0.0` is an explicit opt-in for containers |

## Accepted risks (portfolio-level controls)

The following are handled at the MCP gateway / host layer rather than inside
this single server. Residual risk here is low because the server is read-only,
unauthenticated, and reaches only two trusted public-data hosts.

- **Session crypto-binding** — not applicable: there is no user identity to bind,
  as the server exposes public data with no authentication.
- **Cross-server tool-poisoning detection** — a gateway/host responsibility. This
  server's tool definitions are version-controlled, authored in-repo, and
  reviewed via PR; there is no dynamic or remote tool registration.
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
