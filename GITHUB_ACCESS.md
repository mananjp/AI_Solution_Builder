# GitHub Repository & Access Information
# AI Solution Builder — CHAOS2COMMIT Hackathon 2026

## Repository Details

| Attribute | Value |
|-----------|-------|
| **Repository Name** | AI_Solution_Builder |
| **Repository URL** | https://github.com/mananjp/AI_Solution_Builder |
| **Visibility** | **Public** |
| **Default Branch** | `main` (latest, fully merged with `feature/android`) |
| **Primary Owner** | MANAN PANCHAL ([@mananjp](https://github.com/mananjp)) |
| **Live Production URL** | https://ai-solution-builder.onrender.com |

---

## Team Members & Access Roles

| Name | Role | GitHub Username | Email |
|------|------|-----------------|-------|
| **MANAN PANCHAL** | Team Lead / Full-Stack & AI | [@mananjp](https://github.com/mananjp) | mananjpanchal11@gmail.com |
| **Ansh Dhanani** | Frontend & UI/UX | [@Ansh-Dhanani](https://github.com/Ansh-Dhanani) | dhananiansh01@gmail.com |
| **Nil Lad** | Backend & Database Architect | [@Ladnil03](https://github.com/Ladnil03) | ladnil03@gmail.com |
| **Tirth Bhanderi** | Mobile, DevOps & Testing | [@tirthbhanderi2006](https://github.com/tirthbhanderi2006) | d25aiml081@charusat.edu.in |

All members have full maintainer/collaborator permissions on the repository.

---

## Clone and Setup Instructions

### 1. Clone via HTTPS
```bash
git clone https://github.com/mananjp/AI_Solution_Builder.git
cd AI_Solution_Builder
```

### 2. Clone via SSH (for collaborators)
```bash
git clone git@github.com:mananjp/AI_Solution_Builder.git
cd AI_Solution_Builder
```

### 3. Verify Branch and Latest Commit
```bash
git checkout main
git pull origin main
git log -1 --stat
```

---

## Branching Strategy & Merged History

- **`main`**: Production-ready branch containing all features:
  - Multi-agent LangGraph design pipeline
  - Workable system runtime (PostgreSQL tenant isolation + dynamic REST APIs)
  - MVP code generation pipeline (Next.js + FastAPI)
  - Document ingestion engine (PDF, DOCX, CSV, URLs)
  - Enterprise security scanner (ClamAV + VirusTotal + Archive bomb protection)
  - Payment & credit billing (Razorpay + Stripe)
  - Multilingual support (12 languages)
  - **Android Capacitor native shell + MobileNav bottom bar (merged from `feature/android`)**
- **`feature/android`**: Android Capacitor mobile integration branch, cleanly merged into `main`.

---

## CI/CD Workflows

The repository uses GitHub Actions for continuous integration:
- `.github/workflows/ci.yml` — Runs linting, type checks, backend unit tests with PostgreSQL, and coverage reporting.
- `.github/workflows/deploy.yml` — Automated deployment triggers to Render.com.
