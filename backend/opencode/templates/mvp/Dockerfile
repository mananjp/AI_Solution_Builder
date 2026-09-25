# AI Solution Builder — Unified Container (FastAPI Backend + Next.js Frontend)
# Single-container architecture: Next.js serves on public $PORT (3000) and
# internally rewrites /api/* calls to FastAPI running on 127.0.0.1:8000.
# Eliminates cross-origin CORS issues and build-time NEXT_PUBLIC_API_URL dependencies.

# ── Stage 1: Build Next.js frontend ────────────────────
FROM node:20-alpine AS fe-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 2: Runtime image (Python 3.12 + Node.js) ─────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    PORT=3000

WORKDIR /app

# Install Node.js, npm, curl, and bash
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        bash \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application code
COPY backend/ ./backend/

# Copy frontend built assets and production runtime
COPY --from=fe-builder /app/frontend/.next ./frontend/.next
COPY --from=fe-builder /app/frontend/public ./frontend/public
COPY --from=fe-builder /app/frontend/node_modules ./frontend/node_modules
COPY --from=fe-builder /app/frontend/package.json ./frontend/package.json
COPY --from=fe-builder /app/frontend/next.config.mjs ./frontend/next.config.mjs

# Copy unified entrypoint
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:3000/api/v1/health >/dev/null || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
