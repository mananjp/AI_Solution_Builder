# AI Solution Builder — Dedicated Backend (FastAPI API + OpenCode sidecar)
# Optimized for split deployment: Next.js on Vercel + Backend on Render Free Tier.
# RAM footprint: ~160 MB (leaves >350 MB free headroom on Render's 512MB tier).

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    APP_ROLE=api \
    PORT=8000 \
    HOME=/home/app \
    XDG_CONFIG_HOME=/home/app/.config \
    OPENCODE_SERVER_URL=http://127.0.0.1:4096 \
    MVP_BUILD_DIR=/workspace \
    MALLOC_ARENA_MAX=2 \
    ENABLE_OPENCODE_SIDECAR=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        bash \
        git \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/* \
    && NODE_OPTIONS="" npm install -g @opencode/cli@latest \
    && groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

# OpenCode configuration + custom agents
RUN mkdir -p /home/app/.config/opencode/agents \
             /root/.config/opencode/agents \
             /workspace \
             /app/.data/uploads \
             /app/.data/exports \
    && chmod -R 777 /workspace

COPY backend/opencode/config.json /home/app/.config/opencode/opencode.json
COPY backend/opencode/agents/ /home/app/.config/opencode/agents/
COPY backend/opencode/config.json /root/.config/opencode/opencode.json
COPY backend/opencode/agents/ /root/.config/opencode/agents/

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
    chown -R app:app /home/app /workspace /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:${PORT:-8000}/ready >/dev/null || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
