# Hardened container image for swiss-efv-mcp.
# Runs as a non-root user, on SSE transport, bound to 0.0.0.0 *only* here —
# the container network namespace is isolated and this is an explicit opt-in.
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime
# Non-root user with a high UID.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin efv
COPY --from=build /install /usr/local
USER 10001

# SSE transport; 0.0.0.0 is deliberate and container-scoped.
ENV TRANSPORT=sse \
    HOST=0.0.0.0 \
    PORT=8000 \
    EFV_MCP_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1
EXPOSE 8000

# Liveness probe: the SSE port must be accepting connections (SCALE-004).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex(('127.0.0.1', int(os.environ.get('PORT','8000')))))"

ENTRYPOINT ["swiss-efv-mcp"]
