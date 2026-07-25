# Hardened container image for swiss-efv-mcp.
# Runs as a non-root user, on SSE transport, bound to 0.0.0.0 *only* here —
# the container network namespace is isolated and this is an explicit opt-in.
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
# Non-root user with a high UID.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin efv
COPY --from=build /install /usr/local
USER 10001

# SSE transport; 0.0.0.0 is deliberate and container-scoped.
ENV TRANSPORT=sse \
    HOST=0.0.0.0 \
    PORT=8000 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["swiss-efv-mcp"]
