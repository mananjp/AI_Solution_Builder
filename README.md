# AI Solution Builder

> **From Business Intent to Mounted, Production-Ready Software Systems in Minutes.**

[![CI](https://github.com/mananjp/AI_Solution_Builder/actions/workflows/ci.yml/badge.svg)](https://github.com/mananjp/AI_Solution_Builder/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.3-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

---

## 🌟 Executive Overview

**AI Solution Builder** is an enterprise-grade AI system that converts business ideas, BRDs, SOPs, and legacy schemas into fully functional, tenant-isolated software applications alongside traditional architecture blueprints.

Unlike tools that merely produce mockups or static documentation, AI Solution Builder automatically provisions **live PostgreSQL database schemas**, generates **headless REST APIs**, mounts **interactive UI sandboxes**, and exports production codebases, Terraform scripts, and CI/CD pipelines.

---

## 🏗 System Architecture

```mermaid
flowchart TD

subgraph group_client["Client surfaces"]
  node_web["Next.js dashboard<br/>web client<br/>[page.tsx]"]
  node_api_client["API client<br/>frontend integration<br/>[api.ts]"]
  node_android["Android shell<br/>Capacitor app<br/>[MainActivity.java]"]
end

subgraph group_api["API and governance"]
  node_fastapi["FastAPI API<br/>HTTP service<br/>[main.py]"]
  node_identity["Identity and controls<br/>security layer<br/>[security.py]"]
  node_mvp_api["MVP lifecycle API<br/>route module<br/>[mvp.py]"]
end

subgraph group_design["Design pipeline"]
  node_ingestion["Document and URL ingestion<br/>context normalization<br/>[parser.py]"]
  node_agent_graph{{"Solution design graph<br/>LangGraph workflow<br/>[graph.py]"}}
  node_architecture["Architecture and API design<br/>agent stages"]
  node_llm["LLM provider boundary<br/>AI integration<br/>[llm.py]"]
end

subgraph group_runtime["Workable and MVP build"]
  node_workable_api["Dynamic Workable API<br/>runtime endpoints<br/>[workable.py]"]
  node_provisioner["Schema provisioner<br/>tenant runtime setup"]
  node_synthetic_data["Synthetic data service<br/>preview data<br/>[synthetic.py]"]
  node_worker["Durable build worker<br/>background consumer<br/>[worker.py]"]
  node_mvp_builder["MVP builder<br/>project generator<br/>[mvp_builder.py]"]
  node_opencode{{"OpenCode sidecar<br/>internal code generator<br/>[mvp-builder.md]"}}
  node_workspace["Generated source workspace<br/>shared volume"]
  node_deployment["GitHub and Render deployment<br/>deployment service<br/>[deployer.py]"]
end

subgraph group_infra["Infrastructure"]
  node_postgres[("PostgreSQL + pgvector<br/>system of record<br/>[database.py]")]
  node_redis["Redis<br/>cache and queue<br/>[redis.py]"]
  node_compose["Container topology<br/>local orchestration<br/>[docker-compose.yml]"]
end

node_web -->|"uses"| node_api_client
node_android -->|"hosts"| node_web
node_api_client -->|"/api/v1"| node_fastapi
node_fastapi -->|"enforces"| node_identity
node_fastapi -->|"persists state"| node_postgres
node_fastapi -->|"cache and rate limits"| node_redis
node_fastapi -->|"accepts sources"| node_ingestion
node_ingestion -->|"normalized context"| node_agent_graph
node_agent_graph -->|"design stages"| node_architecture
node_agent_graph -->|"model calls"| node_llm
node_architecture -->|"solution artifacts"| node_postgres
node_fastapi -->|"routes runtime requests"| node_workable_api
node_workable_api -->|"provisions modules"| node_provisioner
node_provisioner -->|"tenant schemas"| node_postgres
node_workable_api -->|"preview seeding"| node_synthetic_data
node_synthetic_data -->|"writes sample data"| node_postgres
node_fastapi -->|"mounts"| node_mvp_api
node_mvp_api -->|"build metadata"| node_postgres
node_mvp_api -->|"queues build"| node_redis
node_redis -->|"consumes jobs"| node_worker
node_worker -->|"runs build"| node_mvp_builder
node_mvp_builder -->|"generation prompt"| node_opencode
node_opencode -->|"writes source"| node_workspace
node_mvp_builder -->|"scaffolds and inspects"| node_workspace
node_workspace -->|"repository source"| node_deployment
node_compose -.->|"starts"| node_fastapi
node_compose -.->|"starts"| node_worker
node_compose -.->|"starts"| node_opencode

click node_web "https://github.com/mananjp/ai_solution_builder/blob/main/frontend/src/app/(dashboard)/solution/%5Bid%5D/page.tsx"
click node_api_client "https://github.com/mananjp/ai_solution_builder/blob/main/frontend/src/lib/api.ts"
click node_android "https://github.com/mananjp/ai_solution_builder/blob/main/frontend/android/app/src/main/java/com/futurrizon/aisolutionbuilder/MainActivity.java"
click node_fastapi "https://github.com/mananjp/ai_solution_builder/blob/main/backend/main.py"
click node_identity "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/core/security.py"
click node_mvp_api "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/api/mvp.py"
click node_postgres "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/core/database.py"
click node_redis "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/core/redis.py"
click node_ingestion "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/ingestion/parser.py"
click node_agent_graph "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/agents/graph.py"
click node_architecture "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/agents/nodes/database_api_agent.py"
click node_llm "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/core/llm.py"
click node_workable_api "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/api/workable.py"
click node_provisioner "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/workable/schema_provisioner.py"
click node_synthetic_data "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/services/synthetic.py"
click node_worker "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/worker.py"
click node_mvp_builder "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/services/mvp_builder.py"
click node_opencode "https://github.com/mananjp/ai_solution_builder/blob/main/backend/opencode/agents/mvp-builder.md"
click node_deployment "https://github.com/mananjp/ai_solution_builder/blob/main/backend/app/services/deployer.py"
click node_compose "https://github.com/mananjp/ai_solution_builder/blob/main/docker-compose.yml"

classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a
classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554
classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d
classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337
classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81
classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a
class node_web,node_api_client,node_android toneBlue
class node_fastapi,node_identity,node_mvp_api toneAmber
class node_ingestion,node_agent_graph,node_architecture,node_llm toneMint
class node_workable_api,node_provisioner,node_synthetic_data,node_worker,node_mvp_builder,node_opencode,node_workspace,node_deployment toneRose
class node_postgres,node_redis,node_compose toneIndigo
```


### Container layout (`docker-compose.yml`)

| Service | Port | Role |
|---|---|---|
| `postgres` | `5433→5432` | pgvector/PostgreSQL 16, tenant RLS, AI + build metadata |
| `redis` | `6379` | rate limiting, caching, queues |
| `backend` | `8000` | FastAPI app (all `/api/v1` routes) |
| `opencode` | `4096` | headless OpenCode agent sidecar; mounts `mvp_workspace` |

The backend and the OpenCode sidecar share the `mvp_workspace` Docker volume: the sidecar writes generated source there (`/workspace/<solution_id>/build_<n>/`), and the backend reads it directly from `.data/mvp_builds/` — no network hop between generation and download/deploy.

---

## 🚀 Key Architecture & Capabilities

### 1. Multi-Agent Intelligence Core (LangGraph)
- **Business Analyst Agent**: Performs domain discovery, gap analysis, stakeholder mapping, and digital maturity assessment.
- **Business Recommendation Agent**: Recommends curated architectural modules from an extensible Industry Template Library when requirements are open-ended.
- **Solutions Architect Agent**: Formulates High-Level (HLD) and Low-Level (LLD) designs, infrastructure specs, and cloud topologies.
- **Process Intelligence Agent**: Generates executable BPMN 2.0 workflows with decision gates and bottleneck detection.
- **UX Agent**: Designs navigation flows, information architectures, and responsive screen wireframes.
- **Database & API Agent**: Formulates normalized relational schemas, ER diagrams, and OpenAPI 3.1 specifications.
- **Full-Stack Code Synthesizer**: Generates operational schemas, CRUD endpoints, and live UI components.

### 2. Workable System Runtime Engine
- **Tenant-Isolated PostgreSQL Schemas**: Declarative schemas applied per workspace solution with dynamic RLS isolation.
- **Instant Headless REST Engine**: Generic FastAPI dynamic router (`/api/v1/workable/{workspace_id}/{module_name}/...`) validating models on the fly.
- **Live Interactive Sandbox**: Interactive UI components rendering real-time forms, filters, and data grids.
- **Synthetic Data Generator**: Auto-populates tenant databases with realistic, localized dummy records.

### 3. Universal Input Ingestion
- Ingests raw text, PRDs, BRDs, PDFs (`PyMuPDF`), Word documents (`python-docx`), CSV/Excel schemas (`openpyxl`/`pandas`), OpenAPI specs (JSON/YAML, auto-detected), and website URLs (`httpx` + BeautifulSoup).
- Every format is normalized to readable text and injected into the agent pipeline as `uploaded_context` via `POST /api/v1/upload/document` and `POST /api/v1/upload/url`.
- *Planned:* vectorized semantic retrieval. The `context_chunks` table reserves a pgvector `embedding` column (`all-MiniLM-L6-v2`, dim 384), but nothing populates it yet — content reaches agents as plain text today.

### 4. Enterprise Governance & Admin
- **Credit & Plan Metering**: Granular credit deductions for generation, regeneration, and exports across Free, Pro, and Enterprise tiers.
- **Granular RBAC**: JWT authentication with roles (`admin`, `member`, `guest`).
- **Audit Logging & Metrics**: Real-time Prometheus metrics (`/metrics`), token consumption tracking, and system health checks.

### 5. Multi-Format Export Engine
- One-click export to **PDF**, **DOCX**, **XLSX**, and **PPTX**.
- Production code packaging with Dockerfiles, GitHub Actions CI workflows, and Terraform scaffolding.
- Direct **Figma REST API** export format for UX assets.
- **One-Click Deployer** targeting GitHub repositories.

### 6. Cross-Platform Delivery
- Web application (Next.js 16 App Router + Tailwind CSS).
- Installable PWA with service worker offline caching.
- Capacitor wrapper for Android (`@capacitor/android`) and web application / PWA distribution.

### 7. OpenCode MVP Builder
- **Template presets**: `todo`, `calculator`, `portfolio` — small, deployable starters listed by `GET /api/v1/mvp/templates`.
- **Custom builds**: generates a full functional app from any validated solution's artifacts (HLD, LLD, ER, API spec, DDL, wireframes).
- **OpenCode sidecar**: a headless `opencode serve` container whose `mvp-builder` agent (model `opencode/big-pickle` — free on OpenCode Zen) "slot-fills" a pre-scaffolded FastAPI + Next.js project with the artifact-specific models, schemas, routers, and pages.
- **GitHub deploy**: `POST /api/v1/mvp/builds/{id}/deploy` pushes the workspace (with `render.yaml`, Dockerfile, CI workflow remapped to the repo root) to a fresh GitHub repository using the user's saved PAT, ready for a Render blueprint auto-deploy.

---

## 🔄 End-to-End Workflow

From a raw business idea to a deployed, working web app in eight phases.

### Phase 0 — Account & credentials
1. Register / log in to get a JWT (`POST /api/v1/auth/register`, `POST /api/v1/auth/login`).
2. (Optional, needed only for Phase 7) Save a GitHub Personal Access Token on your profile:
   ```bash
   PATCH /api/v1/auth/me/settings        {"github_token": "ghp_…", "render_api_key": "…"}
   ```
   Tokens are stored per-user in `user.settings` and never returned by profile endpoints.

### Phase 1 — Ingestion
Feed the system any loose business material — raw text, PRD/BRD, PDF, DOCX, CSV/Excel schema, OpenAPI spec, or a website URL. The ingestion layer parses every format into readable text and feeds it to the agents as `uploaded_context`, so every phase works from the same source material. (Vectorized semantic retrieval over `pgvector` is planned but not yet wired up.)

Ingest via the workspace UI (file dropzone or "paste a URL"), or directly:
- `POST /api/v1/upload/document` (multipart `file`) — PDF, DOCX, CSV/XLSX, TXT/MD, and OpenAPI JSON/YAML (auto-detected)
- `POST /api/v1/upload/url` (`{"url": "https://…"}`) — fetches a page and extracts readable text

### Phase 2 — Agentic design
A `POST` to the solutions/chat API runs the **LangGraph multi-agent pipeline**. Each node writes into the shared `ai_state`:

| Agent | Produces |
|---|---|
| Business Analyst | domain discovery, gap analysis, stakeholders |
| Business Recommendation | module suggestions from the industry template library |
| Solutions Architect | HLD + LLD, infrastructure spec |
| Process Intelligence | executable BPMN 2.0 workflows |
| UX | navigation flows + responsive screen wireframes |
| Database & API | normalized relational schema, ER diagram, DDL, OpenAPI 3.1 |
| Full-Stack Code Synthesizer | operational schemas, CRUD endpoints, live UI components |

### Phase 3 — Workable system runtime
For every **confirmed module**, the runtime provisions a tenant-isolated PostgreSQL schema (Row-Level Security), mounts a generic headless REST engine at `/api/v1/workable/{workspace_id}/{module_name}/…` that validates against those models on the fly, and seeds synthetic data.

### Phase 4 — Artifacts & export
All design artifacts become downloadable deliverables — **PDF / DOCX / XLSX / PPTX**, Figma-ready UX bundles, and full code/ infra packaging with Dockerfiles, GitHub Actions, and Terraform scaffolding.

### Phase 5 — Build an MVP
Two ways to start a functional build:
- **Template** — pick a small starter (`GET /api/v1/mvp/templates` → `todo` / `calculator` / `portfolio`) and pass `{"template": "todo", "app_name": "…"}`.
- **Custom** — let the full `ai_state` (from Phase 2) drive the build for an open-ended request.

Either way you call:
```bash
POST /api/v1/mvp/{solution_id}/build    # deducts MVP-build credits, runs async
GET  /api/v1/mvp/{solution_id}/builds   # poll build list
GET  /api/v1/mvp/builds/{id}/status     # status + generated file tree
```

### Phase 6 — What happens inside a build
1. The backend **scaffolds** a complete FastAPI + Next.js + infra project into the shared volume (`scaffold_build` substitutes app name / slug / title).
2. It compiles a **compact "slot-fill" prompt** from the HLD, LLD, ER entities, API endpoints, wireframe screens, and DDL — deliberately small so it fits the model's token limits.
3. The **OpenCode sidecar agent** (`opencode/big-pickle`) edits only these slots: `models.py`, `schemas.py`, `routers.py`, Alembic migration, and one CRUD page per module.
4. You can **download** the project as a ZIP (`GET …/download`) or **tune it** before shipping via a config overlay (`POST …/configure` with env values / app name).

### Phase 7 — One-click deploy to GitHub + Render
```bash
POST /api/v1/mvp/builds/{id}/deploy     {"repo_name": "quick-todos", "description": "…", "private": false}
```
- The workspace is flattened to a repo file map, with `infra/render.yaml`, `infra/docker-compose.yml`, and `infra/.github/**` remapped to the repository root.
- The deployer creates a fresh GitHub repo via the GitHub REST API using **your** saved PAT and pushes all files (`repo_url` is stored on the build; redeploys require `force: true`).
- Because the repo ships a **Render blueprint + CI workflow**, connecting the repo to Render auto-deploys the app on green CI.

### Phase 8 — Operate
Prometheus metrics (`/metrics`), health/ready probes, audit logs, and credit metering track usage across all tenants.

---

## 🗺 MVP Builder API Summary

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/mvp/templates` | List deployable starter templates |
| `POST` | `/api/v1/mvp/{solution_id}/build` | Start an async build (template or custom) |
| `GET` | `/api/v1/mvp/{solution_id}/builds` | List builds for a solution |
| `GET` | `/api/v1/mvp/builds/{id}/status` | Status + generated file tree |
| `GET` | `/api/v1/mvp/builds/{id}/download` | Download the project as ZIP |
| `POST` | `/api/v1/mvp/builds/{id}/deploy` | Push to a fresh GitHub repo (Render-ready) |
| `POST` | `/api/v1/mvp/builds/{id}/configure` | Apply env/app-name config overlay |
| `DELETE` | `/api/v1/mvp/builds/{id}` | Cancel / destroy a build |
| `PATCH` | `/api/v1/auth/me/settings` | Save GitHub token / Render API key |

---

## 🛠 Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, LangGraph, LangChain, pgvector, Redis, PyMuPDF, python-docx, python-pptx, openpyxl/pandas, beautifulsoup4, PyYAML |
| **Frontend** | Next.js 16 (App Router, Turbopack), React 19, TypeScript 5, Tailwind CSS v4, `@xyflow/react`, Lucide Icons |
| **Mobile & PWA** | Capacitor 8 (Android shell; web app / PWA), PWA Service Worker |
| **MVP Builder** | OpenCode headless sidecar (`opencode serve`), agent `mvp-builder` on model `opencode/big-pickle` (OpenCode Zen, free), HTTP proxy client (`httpx`) |
| **Data & Cache** | PostgreSQL 16 with `vector` extension, Redis 7 |
| **DevOps & Tooling**| Docker & Docker Compose, GitHub Actions, Ruff, Mypy, Pytest (Asyncio + Coverage), ESLint |

---

## 📁 Repository Structure

```
AI_Solution_Builder/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated CI: lint, typecheck, test, build
├── backend/
│   ├── app/
│   │   ├── agents/                   # LangGraph state machine & multi-agent nodes
│   │   ├── api/                      # FastAPI route handlers
│   │   │   ├── auth.py               #   login / register / user settings
│   │   │   ├── mvp.py                #   MVP build, download, deploy, configure
│   │   │   ├── workable.py           #   dynamic runtime schema + REST engine
│   │   │   └── ...
│   │   ├── core/                     # Config, database, redis, security, credits
│   │   ├── ingestion/                # Universal parser (PDF, DOCX, CSV/Excel, OpenAPI, URLs)
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── mvp_build.py          #   MVPBuild (status, workspace_path, repo_url)
│   │   │   ├── solution.py
│   │   │   ├── user.py               #   includes settings JSONB for deploy creds
│   │   │   └── ...
│   │   ├── schemas/                  # Pydantic validation schemas (incl. MVP*)
│   │   ├── services/
│   │   │   ├── deployer.py           # GitHub REST API repo creation + file push
│   │   │   ├── mvp_builder.py        # OpenCode sidecar proxy, prompt builder, scaffold
│   │   │   ├── templates.py          # Starter template presets (todo/calculator/portfolio)
│   │   │   ├── synthetic.py          # Synthetic data generator
│   │   │   └── exporters.py          # PDF / DOCX / XLSX / PPTX / Figma exporters
│   │   └── workable/                 # Dynamic schema provisioner & runtime engine
│   ├── opencode/                     # OpenCode sidecar — built into Docker image
│   │   ├── Dockerfile
│   │   ├── config.json               # model: opencode/big-pickle
│   │   ├── agents/
│   │   │   └── mvp-builder.md        # Agent instructions (slot-fill workflow)
│   │   └── templates/mvp/            # Pre-scaffolded MVP project base
│   │       ├── backend/              #   FastAPI boilerplate + Alembic + auth
│   │       ├── frontend/             #   Next.js 16 boilerplate + Tailwind
│   │       └── infra/                #   render.yaml, docker-compose, CI, README
│   ├── scripts/
│   │   └── seed_demo.py              # Seeds demo user/org/workspace (dev convenience)
│   ├── tests/                        # 150+ async tests (pytest + coverage ≥ 80%)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                      # Next.js App Router (auth, dashboard, chat, …)
│   │   ├── components/               # BPMN viewer, Sandpack, wireframe viewer, …
│   │   └── lib/                      # API client, auth helpers, utilities
│   ├── android/                      # Capacitor Android native project
│   ├── capacitor.config.ts
│   └── package.json
├── docker-compose.yml                # postgres · redis · backend · worker · opencode
├── .env.example                      # Environment configuration template
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose
- [Node.js 20+](https://nodejs.org/) & `npm`
- [Python 3.12+](https://www.python.org/)

### 1. Clone & Configure
```bash
git clone https://github.com/mananjp/AI_Solution_Builder.git
cd AI_Solution_Builder

# Copy environment template
cp .env.example .env
# Edit .env with your LLM API keys (Groq or OpenAI). For the MVP builder,
# OPENCODE_MODEL=opencode/big-pickle is used by the sidecar's own config.json
# (free via OpenCode Zen) — no extra key needed.
```

### 2. Run with Docker Compose
```bash
docker compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`
- OpenCode sidecar health: `http://localhost:4096/global/health` (`{"healthy":true}`)

This starts six cooperating services: `frontend` (Next.js standalone), `postgres`
(pgvector), `redis`, `backend`, `worker` (durable queue consumer), and the `opencode`
sidecar (which shares the `mvp_workspace` volume with the backend and worker so
generated code is visible instantly).

> **Worker Mode:** `WORKER_MODE=worker` (default) requires the `worker` container to be
> running to process queued builds. If running the backend locally outside Docker without
> the worker daemon, set `WORKER_MODE=inline` in your `.env` so builds execute directly.

> **Production guard:** the backend image boots as `APP_ENV=production` and refuses
> to start unless `JWT_SECRET_KEY` is a strong, unique secret (≥ 32 chars). Set one
> in your `.env` before `docker compose up` — the placeholder in `.env.example` will
> fail fast with a clear message. On boot it also runs `alembic upgrade head`
> automatically, so schema migrations apply before the server accepts traffic.

### 3. (Optional) Seed a demo account
```bash
cd backend
python scripts/seed_demo.py
# demo@aibuilder.example / DemoPass123!  — a Free-plan demo org + workspace
```

### 4. Try an MVP build end-to-end
1. Log in and create a workspace/solution, then generate its artifacts (Phases 1–3).
2. `GET /api/v1/mvp/templates` → pick a template (`todo`, `calculator`, `portfolio`).
3. `POST /api/v1/mvp/{solution_id}/build` with `{"template": "todo", "app_name": "…"}`.
4. Poll `GET /api/v1/mvp/builds/{id}/status` until `complete`, then download the ZIP.
5. To deploy: `PATCH /api/v1/auth/me/settings` with a **GitHub PAT**, then
   `POST /api/v1/mvp/builds/{id}/deploy` → connect the repo to Render.

---

## 🌐 Deployment

The repo is deployable today as a **single instance** and has Phase-0 pre-flight
hardening built in:

- **JWT secret guard** — the backend refuses to boot when `APP_ENV=production`
  unless `JWT_SECRET_KEY` is unique and ≥ 32 chars (see `backend/app/core/config.py`).
- **Migrations on boot** — the backend image runs `alembic upgrade head` before
  starting uvicorn (`backend/docker-entrypoint.sh`).
- **Frontend image** — `frontend/Dockerfile` builds a standalone Next.js output
  (`next.config.ts` has `output: "standalone"`); pass the backend URL at build time:
  `docker build -f frontend/Dockerfile --build-arg NEXT_PUBLIC_API_URL=https://api.example.com/api/v1 .`
- **Health checks** — `/health`, `/ready`, `/metrics` on the backend; the compose
  healthchecks gate frontend → backend → postgres/redis/opencode startup ordering.

Recommended production topology:

1. **Serverless Data Stores (Zero instance management)**:
   - **PostgreSQL + pgvector**: [Neon](https://neon.tech/) serverless PostgreSQL with native `pgvector` support and scale-to-zero compute. Raw connection URLs (`postgresql://...sslmode=require`) are normalized automatically to `postgresql+asyncpg://` with `ssl=require`.
   - **Cache & Queue**: [Upstash Redis](https://upstash.com/) serverless Redis with TLS (`rediss://`).
2. **Application Services**:
   - Backend API (`uvicorn`), Background Build Worker (`app.worker`), and OpenCode sidecar (`opencode serve`) co-located on Render or Fly.io.
   - Frontend on Vercel (zero-config) or the `frontend/` standalone Docker image.

### Production Deployment Blueprints

The repository includes ready-to-deploy root manifests:

1. **Render (`render.yaml`)**:
   - Deploys application services without paying for separate managed database instances:
     - `ai-solution-builder-backend`: FastAPI API server (`/ready` health check, connected to Neon & Upstash).
     - `ai-solution-builder-worker`: Background build worker process (durable queue consumer, no HTTP listener).
     - `ai-solution-builder-opencode`: Private internal sidecar service on port 4096.
     - `ai-solution-builder-frontend`: Next.js 16 standalone web application.

2. **Fly.io (`fly.toml`)**:
   - Multi-process configuration deploying both `app` (FastAPI) and `worker` (queue consumer) from a single unified container image (`backend/Dockerfile`), with health checks routed exclusively to the HTTP `app` process.

---

## 🧪 Development & Testing

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows
pip install -r requirements-dev.txt

# Run linting and formatting
ruff check .
ruff format --check .

# Run type checker
mypy app/

# Run complete test suite with coverage
pytest
```

### Frontend
```bash
cd frontend
npm install

# Run linter
npm run lint

# Build production bundle
npm run build

# Start dev server
npm run dev
```

---

## 🛡 Security & License
- Enterprise Row-Level Security (RLS) policies.
- Secure environment separation with `.env.example`.
- Distributed under the MIT License.
