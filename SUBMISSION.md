# AI Solution Builder — Technical Submission
# CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd

## Team Details
| Field | Details |
|-------|---------|
| Team Name | AI Solution Builder |
| Team Member 1 | MANAN PANCHAL (mananjpanchal11@gmail.com) |
| Team Member 2 | Ansh Dhanani (dhananiansh01@gmail.com) |
| Team Member 3 | Nil Lad (ladnil03@gmail.com) |
| Team Member 4 | Tirth Bhanderi (d25aiml081@charusat.edu.in / tbhanderi872@rku.ac.in) |

---

## 1. Project Overview

**AI Solution Builder** is an enterprise-grade AI platform that converts business ideas, BRDs, SOPs, and legacy schemas into fully functional, tenant-isolated software applications alongside traditional architecture blueprints.

Unlike tools that merely produce mockups or static documentation, AI Solution Builder automatically provisions **live PostgreSQL database schemas**, generates **headless REST APIs**, mounts **interactive UI sandboxes**, and exports production codebases, Terraform scripts, and CI/CD pipelines.

**Live Deployment:** https://ai-solution-builder.onrender.com

---

## 2. Technology Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12 | Core runtime |
| FastAPI | 0.141+ | REST API framework |
| PostgreSQL + pgvector | 16 | Primary database with vector search |
| Redis | 7 | Cache, rate limiting, job queue |
| SQLAlchemy (Async) | 2.0.36 | ORM with async support |
| Alembic | 1.14 | Database migrations |
| LangChain + LangGraph | 1.4 / 1.2 | Multi-agent AI orchestration |
| OpenCode Sidecar | latest | Code generation engine |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 16.3 | React framework (SSR/SSG) |
| React | 19.2 | UI library |
| TypeScript | 5.x | Type-safe JavaScript |
| Tailwind CSS | 4.x | Utility-first CSS |
| Framer Motion | 13.x | Animations |
| Capacitor | 8.5 | Mobile (Android) shell |
| @tanstack/react-query | 5.x | Data fetching & caching |
| Radix UI + shadcn | latest | Accessible component primitives |

### Infrastructure
| Technology | Purpose |
|-----------|---------|
| Docker + Docker Compose | Container orchestration |
| Render.com | Cloud deployment (backend + frontend + worker) |
| Cloudinary | Object storage for build artifacts |
| Auth0 | Identity & authentication (RS256 JWT) |
| GitHub Actions | CI/CD pipeline |
| Razorpay + Stripe | Payment gateways |

---

## 3. AI & Third-Party Services

| Service | Purpose | Integration |
|---------|---------|-------------|
| Groq API (OpenAI GPT-OSS-120B) | Primary LLM for solution design and code generation | `backend/app/core/llm.py` |
| OpenCode / Big-Pickle | Code generation sidecar for MVP builds | `backend/app/services/mvp_builder.py` |
| Google Gemini (Flash/Pro) | Product image generation | `backend/app/services/image_gen.py` |
| sentence-transformers (all-MiniLM-L6-v2) | Local embedding model for semantic search | No API key needed |
| Auth0 | OAuth2/OIDC identity provider | RS256 token validation |
| Razorpay | Payment processing (India/UPI) | `backend/app/services/razorpay_gateway.py` |
| ClamAV (optional) | Antivirus scanning of uploaded files | `backend/app/services/security/clamav.py` |
| VirusTotal (optional) | Cloud threat intelligence | `backend/app/services/security/virustotal.py` |

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Surfaces                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Next.js  │  │ API Client   │  │ Android Shell     │  │
│  │ Dashboard │  │ (api.ts)     │  │ (Capacitor)       │  │
│  └────┬─────┘  └──────┬───────┘  └────────┬──────────┘  │
│       └───────────────┼────────────────────┘             │
└───────────────────────┼──────────────────────────────────┘
                        │ /api/v1
┌───────────────────────┼──────────────────────────────────┐
│                 API & Governance                          │
│  ┌──────────┐  ┌──────┴───────┐  ┌───────────────────┐  │
│  │ Identity  │  │   FastAPI    │  │ MVP Lifecycle API │  │
│  │ (Auth0)   │  │   (main.py)  │  │ (mvp.py)          │  │
│  └──────────┘  └──────┬───────┘  └───────────────────┘  │
└───────────────────────┼──────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────┐
│              Design Pipeline                              │
│  ┌──────────┐  ┌──────┴───────┐  ┌───────────────────┐  │
│  │ Document  │  │  LangGraph   │  │  LLM Provider    │  │
│  │ Ingestion │  │  Agent Graph  │  │  (Groq/OpenAI)   │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────┐
│           MVP Build & Runtime                             │
│  ┌──────────┐  ┌──────┴───────┐  ┌───────────────────┐  │
│  │ Build    │  │  OpenCode    │  │ Schema Provisioner│  │
│  │ Worker    │  │  Sidecar     │  │ + Synthetic Data  │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────┐
│              Infrastructure                               │
│  ┌──────────┐  ┌──────┴───────┐  ┌───────────────────┐  │
│  │PostgreSQL│  │    Redis     │  │  Docker Compose   │  │
│  │+pgvector │  │  Cache/Queue │  │  Orchestration    │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Core Modules & Features

### 5.1 AI Agent Pipeline (LangGraph Multi-Agent Workflow)
- **Business Analyst Agent** — Requirement discovery, gap analysis, stakeholder mapping
- **Business Recommendation Agent** — AI-powered solution & technology stack recommendations
- **Solution Architecture Agent** — HLD/LLD, cloud architecture, integration design
- **Process Intelligence Agent** — BPMN workflows, swim-lane diagrams, optimization
- **UX/Wireframe Agent** — Dashboard concepts, navigation flows, wireframe generation
- **Database & API Agent** — ER diagrams, schema design, REST API documentation
- **Planning Agent** — Effort estimation, sprint planning, delivery roadmaps
- **Feature Advisor Agent** — Identifies missing requirements and edge cases
- **Requirement Gap Agent** — Cross-validates specs for completeness

### 5.2 Workable System Runtime
- Live PostgreSQL tenant-isolated schema provisioning
- Dynamic REST API generation from design specs
- Synthetic data seeding for instant previews
- Interactive UI sandbox with hot-reload

### 5.3 MVP Builder Pipeline
- Full-stack code generation (Next.js + FastAPI)
- 5-phase build: Analyze → Scaffold → Code → Verify → Package
- npm install + build verification gate
- One-click deploy to GitHub + Render/Vercel

### 5.4 Document Ingestion
- PDF, DOCX, PPTX, CSV/XLSX, plain text parsing
- URL scraping (BeautifulSoup)
- OpenAPI spec ingestion
- Multi-language detection (12 languages including Gujarati, Hindi, Marathi)

### 5.5 Security & Governance
- Auth0 RS256 JWT authentication with RBAC
- Multi-layer threat scanning (local rules + ClamAV + VirusTotal)
- Archive bomb protection
- Rate limiting & audit logging
- Encrypted credential storage (AES-GCM)

### 5.6 Monetization
- Credit-based billing with usage metering
- Razorpay (India/UPI) + Stripe (global) payment integration
- Webhook signature verification (HMAC-SHA256)
- Plans & organizations management

### 5.7 Collaboration & Export
- Artifact comments & version history
- Export to PDF, DOCX, XLSX, PPTX, Figma
- Full project ZIP download
- One-click GitHub repository creation

### 5.8 Mobile Support
- Progressive Web App (PWA) with service worker
- Capacitor Android native shell
- Responsive bottom navigation for mobile
- Touch-optimized UI components

### 5.9 Multilingual Support
- 12 language support (English, Hindi, Gujarati, Marathi, Tamil, Telugu, Kannada, Bengali, Malayalam, Punjabi, Spanish, French)
- Auto-detection via langdetect
- X-Content-Language header integration

---

## 6. Database Schema

PostgreSQL 16 + pgvector extension. Key tables:

| Table | Purpose |
|-------|---------|
| users | User accounts (Auth0 SSO + local) |
| organizations | Multi-tenant org isolation |
| workspaces | Project workspaces per org |
| solutions | AI-generated solution blueprints |
| solution_artifacts | Versioned design artifacts (ER, API, wireframes) |
| artifact_comments | Collaboration comments |
| mvp_builds | Code generation build records |
| build_jobs | Background build queue |
| credit_transactions | Billing & usage tracking |
| plans | Subscription plans |
| payment_orders | Razorpay/Stripe payment records |
| scan_results | Security scan verdicts |
| audit_logs | Admin audit trail |

Migrations managed by Alembic with advisory-lock-protected auto-migration at startup.

---

## 7. Environment Configuration

See `.env.example` (212 lines) for the complete environment variable reference. Key groups:

1. **Database** — `DATABASE_URL` (PostgreSQL + asyncpg)
2. **Redis** — `REDIS_URL` (cache, rate limiting, queue)
3. **AI** — `GROQ_API_KEY`, `GEMINI_API_KEY`
4. **Auth** — `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ENABLED`
5. **Storage** — `CLOUDINARY_*` or local disk
6. **Payment** — `RAZORPAY_KEY_ID/SECRET`, `STRIPE_API_KEY`
7. **Security** — `SECURITY_SCAN_ENABLED`, `CLAMAV_*`, `VIRUSTOTAL_*`
8. **Deploy** — `GITHUB_TOKEN`, `RENDER_API_KEY`, `VERCEL_TOKEN`

---

## 8. How to Run Locally

### Prerequisites
- Docker Desktop (for PostgreSQL + Redis + OpenCode sidecar)
- Python 3.12+
- Node.js 20+

### Quick Start
```bash
# 1. Clone the repository
git clone https://github.com/mananjp/AI_Solution_Builder.git
cd AI_Solution_Builder

# 2. Copy environment file
cp .env.example .env
# Fill in GROQ_API_KEY, AUTH0_DOMAIN, AUTH0_AUDIENCE, etc.

# 3. Start infrastructure via Docker Compose
docker compose up -d

# 4. Backend setup
cd backend
python -m venv .venv
.venv/Scripts/activate       # Windows
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 5. Frontend setup (new terminal)
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Full Docker Compose (production-like)
```bash
docker compose up --build
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# OpenCode sidecar: http://localhost:4096
```

---

## 9. Testing

```bash
cd backend

# Run all unit tests (requires test database)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ai_solution_builder_test \
  python -m pytest tests/ --no-cov

# Key test suites:
# - test_domain_spec_fidelity.py (14 tests) — domain entity inference
# - test_spec_codegen.py (4 tests) — AppSpec code generation
# - test_mvp_verifier.py (12 tests) — build verification
# - test_storage.py (11 tests) — artifact storage
# - test_render_deployer.py (10 tests) — deployment pipeline
# - test_core_units.py (50+ tests) — core business logic
# - test_mvp_api.py — full API integration tests
# - test_opencode_chat.py — chat streaming tests

# Frontend type check
cd frontend
npx tsc --noEmit
```

**Total test files:** 26 | **Backend Python files:** 110 | **Frontend TS/TSX files:** 54

---

## 10. Repository & Access

| Item | Link |
|------|------|
| GitHub Repository | https://github.com/mananjp/AI_Solution_Builder |
| Branch | `main` (latest, fully merged with feature/android) |
| Live Deployment | https://ai-solution-builder.onrender.com |
| Demo Video | Included in submission (`AI_Solution_Builder_Voiceover.mp4`) |

The repository is **public**. All team members have commit access.

---

## 11. Project Structure

```
AI_Solution_Builder/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── agents/             # LangGraph multi-agent nodes
│   │   │   └── nodes/          # Individual agent implementations
│   │   ├── api/                # REST API route modules
│   │   ├── core/               # Config, database, security, LLM
│   │   ├── ingestion/          # Document parser (PDF, DOCX, etc.)
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic services
│   │   │   ├── legacy_repo/    # Legacy codebase modernizer
│   │   │   └── security/       # Multi-layer threat scanning
│   │   └── workable/           # Live runtime engine
│   ├── alembic/                # Database migration scripts
│   ├── opencode/               # OpenCode sidecar config + templates
│   ├── scripts/                # Utility scripts
│   ├── tests/                  # 26 test files
│   ├── main.py                 # FastAPI application entry point
│   └── requirements.txt        # Python dependencies
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   │   └── (dashboard)/    # Authenticated dashboard routes
│   │   ├── components/         # React components
│   │   │   ├── chat/           # Chat UI components
│   │   │   ├── lab/            # Build progress components
│   │   │   └── mvp/            # MVP build card components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # API client, i18n dictionaries
│   │   └── types/              # TypeScript type definitions
│   ├── android/                # Capacitor Android project
│   └── public/                 # Static assets + service worker
├── docs/                       # Architecture Decision Records
│   └── adr/                    # 6 ADRs
├── docker-compose.yml          # Full local stack orchestration
├── .env.example                # Environment configuration template
├── render.yaml                 # Render.com deployment blueprint
├── fly.toml                    # Fly.io deployment config
└── README.md                   # Comprehensive project documentation
```

---

## 12. Unique Selling Propositions (USPs)

1. **Working Systems, Not Blueprints** — Generates live, tenant-isolated PostgreSQL schemas + REST APIs, not just documentation
2. **One-Click MVP Builder** — AI generates full-stack (Next.js + FastAPI) production codebases with verification gates
3. **Multi-Agent AI Pipeline** — 9+ specialized LangGraph agents collaborating on solution design
4. **Domain Intelligence** — 30+ industry-specific entity lexicons for accurate schema generation
5. **One-Click Cloud Deploy** — GitHub → Render/Vercel deployment pipeline from the dashboard
6. **Enterprise Security** — Multi-layer threat scanning (local rules + ClamAV + VirusTotal)
7. **Legacy Modernizer** — Analyzes existing codebases and generates modernization plans
8. **AI Image Generation** — Product hero images, app icons via Google Gemini
9. **12-Language Support** — Full multilingual UI and AI responses
10. **Mobile-First** — PWA + Capacitor Android app with responsive bottom navigation

---

*Submitted by Team AI Solution Builder for CHAOS2COMMIT Hackathon 2026*
*Date: 1 October 2026*
