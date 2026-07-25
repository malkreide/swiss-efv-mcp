# ADR 0002 — Single-instance deployment; stateful LB deferred (SCALE-002 / SCALE-003)

**Status:** accepted
**Context:** Horizontal scaling of the SSE/HTTP transport.

## Decision

`swiss-efv-mcp` is operated as a **single instance** (local stdio, or one SSE
container behind a reverse proxy). It does **not** implement sticky sessions or a
shared-state session manager, and it does not claim horizontal-scale readiness.

## Rationale

- The server is **stateless per request** except for an in-process 24 h cache of
  the three curated EFV dump files. That cache is a latency optimisation, not
  session state — any instance can serve any request, and a cold instance simply
  refetches.
- There is no user session, no auth, and no write path, so there is nothing to
  pin a client to a specific instance for.
- The SSE transport is offered primarily for a single hosted instance; the
  workload (a few small cached CSV dumps) does not require multiple replicas.

## Consequences / re-evaluation

Before running **multiple SSE replicas** behind a load balancer, add one of:

- edge sticky sessions keyed on `Mcp-Session-Id` (HAProxy/Nginx/Ingress), or
- a shared session store (e.g. Redis) with an explicit TTL,

and add a failover test. Until then, run a single replica; scale vertically.

### Sticky-session example (SCALE-003)

When you do move to multiple replicas, pin each client to one instance on the
`Mcp-Session-Id` header. Nginx:

```nginx
upstream efv_mcp {
    hash $http_mcp_session_id consistent;   # sticky on Mcp-Session-Id
    server efv-mcp-1:8000;
    server efv-mcp-2:8000;
}
server {
    location /sse { proxy_pass http://efv_mcp; proxy_set_header Host $host; }
}
```

Kubernetes Ingress (nginx): `nginx.ingress.kubernetes.io/upstream-hash-by:
"$http_mcp_session_id"`. Traefik: a sticky-session service keyed on the same
header. This is a deployment-layer control; the server code stays stateless
per request.
