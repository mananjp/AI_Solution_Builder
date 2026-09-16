# AI Solution Builder — Builder image (opencode sidecar + background build worker, single container)
# Build from the repo root. The worker and opencode share one container filesystem:
# MVP_BUILD_DIR=/workspace while opencode serves with cwd /workspace.

FROM node:20-slim AS runtime

ENV NODE_ENV=production \
    APP_ENV=production \
    APP_ROLE=builder \
    OPENCODE_ENDPOINT=0.0.0.0 \
    OPENCODE_PORT=4096 \
    MVP_BUILD_DIR=/workspace \
    WORKER_MODE=worker

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g opencode-ai@1.18.31

# OpenCode configuration + custom agents
RUN mkdir -p /root/.config/opencode/agents
COPY backend/opencode/config.json /root/.config/opencode/opencode.json
COPY backend/opencode/agents/ /root/.config/opencode/agents/

# Python backend (worker + alembic)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY backend/app ./app
COPY backend/main.py backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/opencode/templates ./opencode/templates
COPY backend/scripts/run_migrations.py scripts/
COPY backend/entrypoint.sh /app/entrypoint.sh

# Shared workspace for opencode + worker
RUN mkdir -p /workspace && \
    chmod -R a+rwx /workspace && \
    chmod +x /app/entrypoint.sh

WORKDIR /workspace

EXPOSE 4096

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD node -e "fetch('http://localhost:4096/global/health').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["builder"]