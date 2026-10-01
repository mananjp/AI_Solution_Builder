# AI Solution Builder — FastAPI API service (OpenCode/build worker run separately).

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    APP_ROLE=api \
    PORT=8000 \
    MVP_BUILD_DIR=/tmp/mvp-build-cache \
    MALLOC_ARENA_MAX=2 \
    ENABLE_OPENCODE_SIDECAR=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl bash \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

# Workspace + runtime dirs
RUN mkdir -p /tmp/mvp-build-cache \
             /app/.data/uploads \
             /app/.data/exports \
    && chmod -R 777 /tmp/mvp-build-cache

# Python backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/main.py backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/opencode/templates ./opencode/templates
COPY backend/scripts/run_migrations.py scripts/
COPY backend/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh && \
    chown -R app:app /tmp/mvp-build-cache /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:${PORT:-8000}/ready >/dev/null || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
