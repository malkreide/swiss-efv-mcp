# Roadmap & phase architecture (OPS-003)

`swiss-efv-mcp` follows the portfolio's phase model. It is currently in
**Phase 1 (read-only)** and production-ready.

| Phase | Scope | Status |
|---|---|---|
| **1 — Read-only** | Headline series, budget breakdown, spending by institution; five read-only tools over the curated EFV dumps | ✅ current |
| 2 — Detail cubes | Pre-process the 157 MB / 1.23 GB detail cubes (`standardauswertung.csv`, `fir_art_funk.csv`) into SQLite/Parquet and expose deeper drill-downs | planned |
| 3 — Multi-agent | (none planned) | — |

A transition to a later phase requires a re-audit before any write-capable tool
is added. There are no write, send, or filesystem capabilities in any phase of
this server.

## Backlog (from the MCP best-practice audit, non-blocking)

The production-ready audit left a set of `medium` findings tracked here. Items
addressed in the current cycle are struck through.

- ✅ ARCH-002 — tool descriptions with use-case context
- ✅ ARCH-003 — helpful `note` on empty results (no silent empties)
- ✅ SDK-002 — typed Pydantic tool outputs (output schema exposed)
- ✅ SDK-003 — `Context` injection for progress reporting (client-facing logging
  dropped: the `logging` capability is deprecated as of spec `2026-07-28`,
  SEP-2577; per-call diagnostics go to the structlog stderr stream)
- ✅ SEC-004 — reject IP-literal hosts and re-assert the allow-list after redirects
- ✅ SCALE-006 / SEC-007 — `compose.yaml` with resource limits, read-only rootfs, dropped caps
- ✅ OBS-006 — optional OpenTelemetry tracing (`[otel]` extra, env-gated)
- ✅ OPS-001 — per-tool live tests + nightly live workflow
- ✅ ARCH-012 — the MCP protocol version is pinned explicitly, as a **pair**:
  `MCP_MODERN_PROTOCOL_VERSION` (`2026-07-28`, negotiated via `server/discover`)
  and `MCP_HANDSHAKE_PROTOCOL_VERSION` (`2025-11-25`, the classic `initialize`
  handshake). Both are held against the `mcp` SDK's own constants and exercised
  over a real connection, so a protocol-changing SDK bump fails CI loudly.
- SEC-022 — server-identity namespace is provided by the MCP Registry name
  (`io.github.malkreide/swiss-efv-mcp`); renaming the unprefixed `dump_status`
  tool is deferred to avoid a breaking change after the 0.2.0 release.

## Accepted risks (ADRs)

- [ADR 0001 — DNS pinning](adr/0001-dns-pinning.md) (SEC-005)
- [ADR 0002 — single-instance deployment; stateful LB deferred](adr/0002-scaling-and-deployment.md) (SCALE-002 / SCALE-003)
