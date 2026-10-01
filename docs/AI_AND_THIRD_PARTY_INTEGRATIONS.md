# AI & Third-Party Integrations Reference
# AI Solution Builder — CHAOS2COMMIT Hackathon 2026

This document provides a comprehensive technical breakdown of all Artificial Intelligence models, external APIs, and third-party cloud services integrated into **AI Solution Builder**.

---

## 1. Large Language Models (LLMs) & AI Engines

### 1.1 Groq API (Primary LLM Provider)
- **Role:** High-speed reasoning, multi-agent solution architecture generation, requirement gap analysis, and code synthesis.
- **Model Used:** `openai/gpt-oss-120b` (fallback: `llama-3.3-70b-versatile`, `mixtral-8x7b-32768`)
- **Integration File:** `backend/app/core/llm.py`
- **Capabilities:**
  - Token generation at 300+ tokens/second for real-time streaming to the dashboard.
  - JSON Schema enforcement for structured artifact output (ER diagrams, OpenAPI specs, user stories).
  - Temperature tuning: `0.2` for deterministic schemas, `0.7` for UX brainstorming.

### 1.2 OpenCode / Big-Pickle Sidecar (Code Generation Engine)
- **Role:** Autonomous full-stack codebase generation (Next.js + FastAPI) inside isolated sandbox environments.
- **Protocol:** HTTP REST & SSE streaming over port `4096`.
- **Integration File:** `backend/app/services/mvp_builder.py`, `backend/app/services/opencode_client.py`
- **Build Phases Orchestrated:**
  1. *Analyze:* Parses AppSpec, entity lexicons, and theme choices.
  2. *Scaffold:* Generates Next.js App Router layout, Tailwind configuration, and FastAPI router structure.
  3. *Code:* Synthesizes type-safe TypeScript UI components and SQLAlchemy async models.
  4. *Verify:* Executes `npm install` and `npm run build` verification gates in temporary staging containers.
  5. *Package:* Generates production-ready ZIP archive and pushes repository to GitHub.

### 1.3 Google Gemini API (Visual Asset & Image Generation)
- **Role:** Context-aware product hero banners, application icons, and preview visuals.
- **Models Used:** `gemini-1.5-flash`, `gemini-1.5-pro`, `imagen-3`
- **Integration File:** `backend/app/services/image_gen.py`
- **Workflow:** Extracts brand color palette and industry sector from the generated AppSpec, then formulates curated image prompts to produce production UI assets.

### 1.4 Sentence-Transformers (`all-MiniLM-L6-v2`)
- **Role:** Local vector embeddings for semantic document search, requirement chunk retrieval, and RAG.
- **Execution Mode:** Runs 100% locally in-process (zero external API dependency, zero per-token cost).
- **Dimension:** 384-dimensional dense vectors stored in PostgreSQL via the `pgvector` extension.
- **Integration File:** `backend/app/ingestion/embeddings.py`

---

## 2. Authentication & Identity Provider

### 2.1 Auth0 (Enterprise Identity Platform)
- **Role:** User authentication, organization tenancy, session lifecycle, and Single Sign-On (SSO).
- **Protocol:** OpenID Connect (OIDC) / OAuth 2.0.
- **Token Verification:** Asymmetric RS256 JWT signature verification with automatic JWKS key caching.
- **Integration Files:**
  - `backend/app/core/auth0.py` — Token validation, audience checking, scope enforcement.
  - `frontend/src/lib/auth0.ts` — Frontend session management & login redirect flows.
- **Features:**
  - RBAC (Role-Based Access Control): `admin`, `architect`, `developer`, `viewer`.
  - Organization isolation mapping to multi-tenant database schemas.

---

## 3. Financial & Payment Gateways

### 3.1 Razorpay (India & UPI Payments)
- **Role:** Domestic payment processing for credit packs and organization subscription upgrades.
- **Currencies:** INR (₹).
- **Payment Methods:** UPI (Google Pay, PhonePe, Paytm), Netbanking, Credit/Debit Cards.
- **Integration File:** `backend/app/services/razorpay_gateway.py`
- **Webhook Security:** HMAC-SHA256 signature verification on `payment.captured` and `order.paid` events.

### 3.2 Stripe (Global Payments)
- **Role:** International credit card processing and recurring subscription management.
- **Currencies:** USD ($), EUR (€), GBP (£).
- **Integration File:** `backend/app/services/stripe_gateway.py`
- **Webhook Security:** Cryptographic webhook secret verification (`stripe-signature`).

---

## 4. Security & Threat Intelligence

### 4.1 ClamAV (Antivirus Engine)
- **Role:** Real-time scanning of all uploaded requirement documents (PDF, DOCX, ZIP).
- **Protocol:** `clamd` daemon TCP socket communication.
- **Integration File:** `backend/app/services/security/clamav.py`
- **Detection:** Known viruses, trojans, macro malware in office documents.

### 4.2 VirusTotal API v3
- **Role:** Cloud-based multi-engine hash reputation and malware URL verification.
- **Integration File:** `backend/app/services/security/virustotal.py`
- **Features:** SHA-256 hash lookup with local Redis cache to prevent redundant external API quota usage.

### 4.3 In-House Threat & Bomb Defense Engine
- **Role:** File validation before LLM parsing.
- **Integration File:** `backend/app/services/security/rules.py`
- **Protections:**
  - Archive bomb detection (compression ratio > 100:1).
  - Suspicious executable/script extension blocking (`.exe`, `.bat`, `.sh`, `.vbs`).
  - Strict MIME-type validation against binary magic bytes.

---

## 5. Storage & Cloud Infrastructure

### 5.1 Cloudinary (Object & Artifact Storage)
- **Role:** Cloud storage and CDN delivery for generated build ZIPs, wireframe images, and exported reports.
- **Integration File:** `backend/app/services/storage.py`
- **Fallback:** Seamlessly falls back to local disk storage if Cloudinary credentials are not configured.

### 5.2 Render.com (Production PaaS)
- **Role:** Hosting backend FastAPI service, Celery/Redis background worker, and PostgreSQL database.
- **Configuration:** Defined declaratively in `render.yaml`.
- **Deploy Hooks:** One-click deployment API integration (`backend/app/services/render_deployer.py`).

### 5.3 Fly.io
- **Role:** Edge container deployment alternative configured via `fly.toml`.

---

## 6. Mobile & Client Runtime

### 6.1 Capacitor (Ionic)
- **Role:** Native Android runtime wrapping the Next.js responsive web application.
- **Configuration:** `frontend/capacitor.config.ts` and `frontend/android/`
- **Plugins:**
  - `@capacitor/app` — Lifecycle events and back button handling.
  - `@capacitor/haptics` — Tactile feedback on mobile interactions.
  - `@capacitor/status-bar` — Dynamic status bar theme synchronization.

---

## 7. Summary Matrix of Third-Party Dependencies

| Service / Dependency | Mandatory? | Purpose | Fallback Behavior |
|----------------------|------------|---------|-------------------|
| Groq API | Yes | Core AI Reasoning & Generation | Mock / Template Mode |
| PostgreSQL 16 + pgvector | Yes | Relational Data + Embeddings | SQLite (unit tests only) |
| Redis 7 | Yes | Cache, Rate Limiting, Task Queue | In-memory Mock |
| OpenCode Sidecar | Optional | Autonomous MVP code generator | Rule-based AppSpec scaffold |
| Auth0 | Recommended | Production SSO & Auth | Local JWT Auth (dev mode) |
| Google Gemini | Optional | Image generation | Fallback SVG / Unsplash placeholders |
| Razorpay | Optional | Indian Rupee Billing | Test mode simulated orders |
| Stripe | Optional | Global USD Billing | Test mode simulated orders |
| ClamAV | Optional | File virus scanning | Local static rule heuristics |
| VirusTotal | Optional | Threat intelligence | Local rule heuristics |
| Cloudinary | Optional | CDN artifact hosting | Local disk storage |
