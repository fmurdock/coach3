FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 coach3 \
    && useradd --uid 10001 --gid coach3 --shell /usr/sbin/nologin --create-home coach3

COPY --from=builder /install /usr/local

# Remove installed duplicate src package so /app/src is the single canonical source tree
RUN rm -rf /usr/local/lib/python3.12/site-packages/src

COPY --chown=coach3:coach3 src/ ./src/
COPY --chown=coach3:coach3 alembic/ ./alembic/
COPY --chown=coach3:coach3 alembic.ini ./
COPY --chown=coach3:coach3 docker-entrypoint.sh ./
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

USER coach3

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8000}/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
