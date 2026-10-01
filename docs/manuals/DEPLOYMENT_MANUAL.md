# AI Solution Builder — Deployment & Operations Manual
# CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd

This document outlines deployment architectures, production configuration guidelines, container orchestration, and monitoring procedures for **AI Solution Builder**.

---

## 1. Production Architecture Overview

The production deployment consists of:
1. **Frontend Service:** Next.js 16 container running Node.js 20 on edge CDN / PaaS.
2. **Backend Service:** FastAPI running under Uvicorn with async worker processes.
3. **Background Worker:** Background task processor for code builds, ZIP compilation, and virus scans.
4. **Relational Database:** Managed PostgreSQL 16 with `pgvector` enabled.
5. **In-Memory Cache & Queue:** Redis 7 for Celery task queuing, session storage, and rate limiting.
6. **OpenCode Code Generation Sidecar:** Isolated container executing code synthesis on internal port 4096.

---

## 2. Docker Compose Deployment (Self-Hosted / On-Premise)

The included `docker-compose.yml` provides a production-grade stack that can be launched on any Linux VM or cloud server.

### Prerequisites
- Ubuntu 22.04 LTS / Debian 12 / RHEL 9
- Docker Engine 24+ & Docker Compose v2.20+
- Minimum 4 CPU cores & 8 GB RAM (16 GB recommended for concurrent MVP builds)

### Launch Commands
```bash
# 1. Clone repository
git clone https://github.com/mananjp/AI_Solution_Builder.git
cd AI_Solution_Builder

# 2. Configure environment
cp .env.example .env
nano .env # Set secure passwords and production API keys

# 3. Build and launch all services in detached mode
docker compose up -d --build

# 4. Monitor startup logs
docker compose logs -f backend
```

### Exposed Service Endpoints
| Service | Internal Port | Host Port | Path |
|---------|---------------|-----------|------|
| Frontend | 3000 | 3000 | `/` |
| Backend API | 8000 | 8000 | `/api/v1` |
| Swagger Docs | 8000 | 8000 | `/docs` |
| PostgreSQL | 5432 | 5432 | `postgres://...` |
| Redis | 6379 | 6379 | `redis://...` |
| OpenCode Sidecar | 4096 | 4096 | `/` (internal only) |

---

## 3. Render.com Cloud Deployment

The repository includes a declarative `render.yaml` blueprint:

1. Log in to your [Render.com](https://render.com) dashboard.
2. Navigate to **Blueprints** → **New Blueprint Instance**.
3. Connect the repository `https://github.com/mananjp/AI_Solution_Builder`.
4. Render will automatically parse `render.yaml` and provision:
   - `ai-solution-builder-api` (Web Service, Python environment)
   - `ai-solution-builder-web` (Web Service, Node environment)
   - `ai-solution-builder-db` (Managed PostgreSQL 16)
   - `ai-solution-builder-redis` (Managed Redis)
5. Fill in the required secret environment variables (`GROQ_API_KEY`, `AUTH0_CLIENT_SECRET`, etc.).
6. Click **Apply**. Database migrations execute automatically during container startup using Alembic's advisory lock mechanism.

---

## 4. Production Environment Variables Reference

| Variable | Description | Example / Default |
|----------|-------------|-------------------|
| `ENVIRONMENT` | Deployment environment | `production` |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `REDIS_URL` | Redis cache and queue connection | `redis://:pass@host:6379/0` |
| `GROQ_API_KEY` | Groq Cloud AI API key | `gsk_...` |
| `AUTH0_DOMAIN` | Auth0 tenant domain | `dev-xyz.us.auth0.com` |
| `AUTH0_AUDIENCE` | Auth0 API identifier | `https://api.ai-solution-builder.com` |
| `AUTH0_ENABLED` | Toggle Auth0 authentication | `true` |
| `CORS_ORIGINS` | Allowed frontend domains | `https://ai-solution-builder.onrender.com` |
| `SECURITY_SCAN_ENABLED` | Enable file threat scanning | `true` |
| `CLOUDINARY_URL` | Object storage connection string | `cloudinary://key:secret@cloud_name` |
| `RAZORPAY_KEY_ID` | Razorpay API key ID | `rzp_live_...` |
| `RAZORPAY_KEY_SECRET` | Razorpay webhook & API secret | `secret...` |

---

## 5. Health Checks & Monitoring

The application provides automated health check endpoints:

- **Backend Health Check:** `GET /health` or `HEAD /health`
  - Returns HTTP 200 with JSON payload:
    ```json
    {
      "status": "healthy",
      "database": "connected",
      "redis": "connected",
      "version": "1.0.0"
    }
    ```
- **Readiness Probe:** `GET /api/v1/health/ready`
- **Liveness Probe:** `GET /api/v1/health/live`

### Database Backup & Restore
```bash
# Automated Daily Backup:
pg_dump -U postgres -h localhost -Fc ai_solution_builder > backup_$(date +%Y%m%d).dump

# Restore from Backup:
pg_restore -U postgres -h localhost -d ai_solution_builder -c backup_20261001.dump
```
