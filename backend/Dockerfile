# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.14-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# Dependencies first so this layer is cached until pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/app.db LOG_FORMAT=json
WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir /data && chown app /data
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY scripts ./scripts
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
# Create tables if missing, then serve. --forwarded-allow-ips='*' is safe here only because
# the port is not published: just the nginx container can reach it, and it sets the client IP.
CMD ["sh", "-c", "python -m scripts.init_db && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
