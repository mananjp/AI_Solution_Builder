# AI Solution Builder — App image (FastAPI API + Next.js frontend, single container)
# Build from the repo root. Requires next.config.ts `output: "standalone"`.
# Runtime: python:3.12-slim + nodejs for the standalone Next.js server.

# ── Stage 1: frontend deps ─────────────────────────
FROM node:20-alpine AS fe-deps
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# ── Stage 2: frontend build ────────────────────────
FROM node:20-alpine AS fe-build
WORKDIR /frontend
ARG NEXT_PUBLIC_API_URL=/api/v1
ARG NEXT_PUBLIC_APP_NAME="AI Solution Builder"
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=fe-deps /frontend/node_modules ./node_modules
COPY frontend/ ./
RUN npm run build

# ── Stage 3: runtime ───────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    APP_ENV=production \
    APP_ROLE=app \
    PORT=3000 \
    HOME=/home/app \
    XDG_CONFIG_HOME=/home/app/.config \
    OPENCODE_SERVER_URL=http://127.0.0.1:4096 \
    MVP_BUILD_DIR=/workspace

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        bash \
        git \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g opencode-ai@1.18.31 \
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

# Next.js standalone + runtime assets. The standalone output ships a subset
# package.json (no lockfile), so a plain prod install is used instead of npm ci.
COPY --from=fe-build /frontend/.next/standalone ./frontend
COPY --from=fe-build /frontend/.next/static ./frontend/.next/static
COPY --from=fe-build --chown=app:app /frontend/public ./frontend/public
COPY --from=fe-build /frontend/package.json ./frontend/package.json
RUN cd frontend && npm install --omit=dev --ignore-scripts --no-audit --no-fund

RUN chmod +x /app/entrypoint.sh && \
    chown -R app:app /home/app /workspace /app

USER app

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:3000/ready >/dev/null || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["app"]