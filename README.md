# AI Solution Builder

> **From Business Intent to Mounted, Production-Ready Software Systems in Minutes.**

[![CI](https://github.com/mananjp/AI_Solution_Builder/actions/workflows/ci.yml/badge.svg)](https://github.com/mananjp/AI_Solution_Builder/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.3-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

---

## 🌟 Executive Overview

**AI Solution Builder** is an enterprise-grade AI system that converts business ideas, BRDs, SOPs, and legacy schemas into fully functional, tenant-isolated software applications alongside traditional architecture blueprints.

Unlike tools that merely produce mockups or static documentation, AI Solution Builder automatically provisions **live PostgreSQL database schemas**, generates **headless REST APIs**, mounts **interactive UI sandboxes**, and exports production codebases, Terraform scripts, and CI/CD pipelines.

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
- Ingests raw text, PRDs, BRDs, PDFs (`PyMuPDF`), Word documents (`python-docx`), CSV schemas, OpenAPI specs, and website URLs.
- Chunks and stores semantic context via `pgvector` embeddings (`all-MiniLM-L6-v2`).

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
- Capacitor wrapper for Android (`@capacitor/android`) and iOS distribution.

---

## 🛠 Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, LangGraph, LangChain, pgvector, Redis, PyMuPDF, python-docx |
| **Frontend** | Next.js 16 (App Router, Turbopack), React 19, TypeScript 5, Tailwind CSS v4, `@xyflow/react`, Lucide Icons |
| **Mobile & PWA** | Capacitor 8 (Android/iOS shell), PWA Service Worker |
| **Data & Cache** | PostgreSQL 16 with `vector` extension, Redis 7 |
| **DevOps & Tooling**| Docker & Docker Compose, GitHub Actions, Ruff, Mypy, Pytest (Asyncio + Coverage), ESLint |

---

## 📁 Repository Structure

```
AI_Solution_Builder/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI: lint, typecheck, test, build
├── backend/
│   ├── app/
│   │   ├── agents/                # LangGraph state machine & multi-agent nodes
│   │   ├── api/                   # FastAPI route handlers (auth, workspaces, chat, workable...)
│   │   ├── core/                  # Configuration, database, redis, security, credits
│   │   ├── ingestion/             # Universal parser (PDF, DOCX, CSV, URLs)
│   │   ├── models/                # SQLAlchemy ORM models
│   │   ├── schemas/               # Pydantic validation schemas
│   │   ├── services/              # Export engine, synthetic data, deployer
│   │   └── workable/              # Dynamic schema provisioner & runtime engine
│   ├── tests/                     # 100+ unit and integration tests (pytest)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router (auth, dashboard, chat, admin...)
│   │   ├── components/            # UI components (BPMN viewer, Sandpack, artifacts...)
│   │   └── lib/                   # API clients, auth helpers, utilities
│   ├── android/                   # Capacitor Android native project
│   ├── capacitor.config.ts
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml             # Postgres (pgvector) + Redis + Backend + Frontend
├── .env.example                   # Environment configuration template
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
# Edit .env with your LLM API keys (Groq or OpenAI)
```

### 2. Run with Docker Compose
```bash
docker compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`

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
