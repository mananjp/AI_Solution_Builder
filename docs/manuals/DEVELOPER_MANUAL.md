# AI Solution Builder — Developer Manual
# CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd

This document serves as the technical guide for software engineers, backend developers, and systems architects working on or extending **AI Solution Builder**.

---

## 1. System Architecture Overview

AI Solution Builder is structured as a decoupled monorepo:
- **`backend/`**: FastAPI (Python 3.12) async REST API, LangGraph orchestration, SQLAlchemy async ORM, and build services.
- **`frontend/`**: Next.js 16 (React 19, TypeScript) App Router, Tailwind CSS, TanStack Query, and Capacitor Android shell.
- **`docs/`**: Architecture Decision Records (ADRs) and technical specifications.

---

## 2. Local Development Setup

### Prerequisites
- Python 3.12 or newer
- Node.js 20 LTS or newer (with npm)
- Docker & Docker Compose
- Git

### Step-by-Step Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mananjp/AI_Solution_Builder.git
   cd AI_Solution_Builder
   ```

2. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your GROQ_API_KEY, AUTH0 secrets, and database credentials
   ```

3. **Start Core Infrastructure (PostgreSQL & Redis):**
   ```bash
   docker compose up -d postgres redis
   ```

4. **Backend Setup:**
   ```bash
   cd backend
   python -m venv .venv
   
   # On Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # On Linux/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   pip install -r requirements-dev.txt

   # Run Database Migrations:
   alembic upgrade head

   # Start the FastAPI Development Server:
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Frontend Setup (in a separate terminal):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## 3. Directory Layout & Module Responsibilities

```
backend/app/
├── agents/             # LangGraph agent definitions
│   ├── graph.py        # LangGraph state machine & router
│   ├── state.py        # AgentState TypedDict schema
│   └── nodes/          # Specialized agent logic (BA, Architect, UX, etc.)
├── api/                # FastAPI router endpoints
│   ├── v1/             # Versioned REST endpoints (solutions, builds, auth)
│   └── deps.py         # Dependency injection (DB session, current user)
├── core/               # Cross-cutting concerns
│   ├── config.py       # Pydantic Settings management
│   ├── database.py     # Async SQLAlchemy engine & session factory
│   ├── auth0.py        # RS256 JWT validation & RBAC
│   └── llm.py          # Groq / OpenAI LLM client factory
├── ingestion/          # Document extraction & embedding pipeline
├── models/             # SQLAlchemy ORM models
├── schemas/            # Pydantic input/output schemas
├── services/           # Domain business services
│   ├── mvp_builder.py  # End-to-end code generation pipeline
│   ├── workable/       # Tenant schema provisioning & synthetic seeding
│   ├── security/       # ClamAV, VirusTotal & archive rules
│   └── image_gen.py    # Google Gemini asset generation
└── workable/           # Live database dynamic schema engine
```

---

## 4. Multi-Agent Pipeline Implementation

The multi-agent workflow is implemented using **LangGraph**:
1. **State Definition (`backend/app/agents/state.py`):**
   ```python
   class SolutionState(TypedDict):
       session_id: str
       user_prompt: str
       industry: str
       documents: list[dict]
       artifacts: dict[str, Any]
       current_agent: str
       iteration: int
   ```
2. **Adding a New Agent Node:**
   - Create a new file in `backend/app/agents/nodes/my_agent.py`.
   - Implement the async node function: `async def my_agent_node(state: SolutionState) -> dict: ...`
   - Register the node in `backend/app/agents/graph.py` via `builder.add_node("my_agent", my_agent_node)`.
   - Define transition edges and conditional routing logic.

---

## 5. Workable System Runtime Engine

The workable system allows live execution without code builds:
- When a user requests a preview, `backend/app/services/workable/provisioner.py` connects to PostgreSQL and runs `CREATE SCHEMA IF NOT EXISTS sandbox_<id>`.
- Tables are mapped dynamically from the solution's ER artifact JSON.
- `backend/app/services/workable/synthetic.py` uses localized entity dictionaries to insert realistic mock records.
- Generic REST endpoints under `/api/v1/workable/<id>/<table>` execute parameterized SQL queries isolated strictly to that schema.

---

## 6. Running Tests & Quality Verification

### Backend Automated Test Suite
```bash
cd backend

# Run entire test suite
pytest tests/ -v

# Run fast unit tests without requiring a real database
pytest tests/test_core_units.py -v

# Run domain entity fidelity tests
pytest tests/test_domain_spec_fidelity.py -v

# Run code generator verification tests
pytest tests/test_spec_codegen.py tests/test_mvp_verifier.py -v
```

### Frontend Type Checking & Linting
```bash
cd frontend

# TypeScript type check
npx tsc --noEmit

# Next.js production build check
npm run build
```

---

## 7. Code Standards & Git Workflow

- **Python:** Formatted with `ruff`, type-checked with `mypy`. All API route functions must include explicit response models and status codes.
- **TypeScript:** Strict mode enabled. No `any` types in production components.
- **Git Branching:** Feature branches branch off `main`. PRs must pass GitHub Actions CI checks before merging.
