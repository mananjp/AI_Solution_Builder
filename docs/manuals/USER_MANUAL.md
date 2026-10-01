# AI Solution Builder — User Manual
# CHAOS2COMMIT Hackathon 2026 — Futurrizon Technologies Pvt Ltd

Welcome to the **AI Solution Builder User Manual**. This guide walks business analysts, product managers, and developers through each phase of designing, generating, testing, and deploying enterprise software solutions using AI Solution Builder.

---

## Table of Contents
1. [Getting Started & Authentication](#1-getting-started--authentication)
2. [Project Dashboard Overview](#2-project-dashboard-overview)
3. [Creating a New Solution (Solution Wizard)](#3-creating-a-new-solution-solution-wizard)
4. [Document & Spec Ingestion](#4-document--spec-ingestion)
5. [The Multi-Agent Design Pipeline](#5-the-multi-agent-design-pipeline)
6. [Exploring Generated Architecture Artifacts](#6-exploring-generated-architecture-artifacts)
7. [The Workable System Runtime & Live Sandbox](#7-the-workable-system-runtime--live-sandbox)
8. [Triggering the One-Click MVP Builder](#8-triggering-the-one-click-mvp-builder)
9. [Deploying to GitHub, Render & Vercel](#9-deploying-to-github-render--vercel)
10. [Exporting Blueprints & Handover Assets](#10-exporting-blueprints--handover-assets)
11. [Mobile Experience & Android App](#11-mobile-experience--android-app)

---

## 1. Getting Started & Authentication

1. Open your browser and navigate to the application URL:
   - **Cloud Hosted:** `https://ai-solution-builder.onrender.com`
   - **Local Environment:** `http://localhost:3000`
2. Click **Sign In** on the top navigation bar.
3. Authenticate using your corporate account via **Auth0 Single Sign-On (SSO)** or email/password.
4. Upon authentication, you will be automatically routed to your default Organization Workspace.

---

## 2. Project Dashboard Overview

The dashboard is your central command center:
- **Solution Portfolio:** Shows active solution blueprints, their status (Draft, Generating, Approved, Deployed), and last modified timestamp.
- **Credit Meter:** Real-time visibility into your organization's compute and build credits.
- **System Metrics:** Displays total provisioned databases, live APIs, and generated MVP codebases.
- **Quick Actions:** Create a new solution, upload a legacy repository, or purchase credit packs.

---

## 3. Creating a New Solution (Solution Wizard)

To initiate an AI-assisted architecture design:
1. Click the **+ New Solution** button in the dashboard or sidebar.
2. Provide a descriptive **Project Title** (e.g., *"Omnichannel Logistics Dispatch Platform"*).
3. Select your target **Industry Sector** (e.g., Logistics, FinTech, Healthcare, E-Commerce, EdTech). Selecting an industry automatically loads tailored entity lexicons.
4. Select your preferred **UI Theme & Tone** (Modern Tech, Enterprise Slate, Midnight Violet, Clean Minimal).
5. Choose your target deployment cloud (AWS, Azure, GCP, Render, Self-Hosted).

---

## 4. Document & Spec Ingestion

You can seed the solution with existing documentation:
- **File Upload:** Drag and drop BRDs, PRDs, SOPs, or architecture documents (`.pdf`, `.docx`, `.pptx`, `.csv`, `.xlsx`, `.txt`).
- **Web URL Ingestion:** Enter a public URL to import technical documentation or API reference sites.
- **OpenAPI / Swagger Ingestion:** Upload an existing OpenAPI YAML/JSON file to preserve existing API contracts.
- **Multi-Layer Security Scanning:** Uploaded files automatically pass through ClamAV antivirus and archive-bomb checks before being parsed into vector chunks.

---

## 5. The Multi-Agent Design Pipeline

Once you click **Generate Blueprint**, the LangGraph multi-agent pipeline begins in real time:
- **Business Analyst Agent:** Distills unstructured documents into concise problem statements, user personas, and acceptance criteria.
- **Business Recommendation Agent:** Evaluates build vs. buy decisions and recommends optimal technology stacks.
- **Solution Architecture Agent:** Produces high-level system diagrams (HLD) and low-level component models (LLD).
- **Process Intelligence Agent:** Maps business processes into BPMN workflow diagrams and identifies automation bottlenecks.
- **UX / Wireframe Agent:** Generates responsive wireframe layouts, visual hierarchy, and component mockups.
- **Database & API Agent:** Formulates normalized ER schemas, SQL tables, and OpenAPI REST specifications.
- **Planning Agent:** Calculates work breakdown structures, story points, sprint allocations, and milestones.

You can monitor the live streaming agent thought processes and intermediate artifacts right in the chat panel.

---

## 6. Exploring Generated Architecture Artifacts

Navigate between artifact tabs in the Solution View:
- **Overview:** Executive summary, problem statement, and scope boundaries.
- **Architecture Diagram:** Interactive Mermaid diagram showing service topology and data flow.
- **ER Schema:** Database entity diagram showing primary keys, foreign keys, and indexes.
- **REST APIs:** Full interactive OpenAPI specification with curl examples and response models.
- **BPMN Workflows:** End-to-end swimlane workflow processes.
- **Sprint Plan:** Agile sprint schedule, team allocations, and risk matrix.
- **Comments & Approvals:** Team members can leave threaded comments on any artifact and submit formal sign-off.

---

## 7. The Workable System Runtime & Live Sandbox

Unlike traditional static design tools, AI Solution Builder lets you immediately test what was designed:
1. Click **Launch Live Sandbox** on the top action bar.
2. The platform provisions a dedicated, tenant-isolated PostgreSQL schema under `sandbox_<solution_id>`.
3. The engine automatically seeds realistic, domain-specific synthetic data.
4. A dynamic headless REST API is exposed immediately, allowing you to test GET, POST, PUT, and DELETE requests in real time.
5. The interactive UI sandbox displays functional data tables and forms directly bound to this live schema.

---

## 8. Triggering the One-Click MVP Builder

When the architecture is finalized, convert it into production code:
1. Click **Build Full-Stack MVP**.
2. Select your preferred options:
   - Include Next.js 16 App Router frontend
   - Include FastAPI async backend
   - Include AI-generated hero visuals (via Google Gemini)
   - Enable PWA & Capacitor Android shell
3. Watch the real-time build log streaming through the 5 phases:
   - `[1/5] Analyze Specs`
   - `[2/5] Scaffold Repositories`
   - `[3/5] Generate Code & Models`
   - `[4/5] Verification Gate (npm build & type check)`
   - `[5/5] Package Production Bundle`
4. When finished, preview the generated application in the side-by-side browser preview.

---

## 9. Deploying to GitHub, Render & Vercel

From the build completion screen:
- **Push to GitHub:** Enter your repository name. AI Solution Builder creates the remote repository on your GitHub account, configures workflows, and pushes all branches with a single click.
- **Deploy to Render:** Click **Deploy Backend** to provision live PostgreSQL and FastAPI web services.
- **Deploy to Vercel:** Click **Deploy Frontend** to launch the Next.js frontend globally on edge servers.

---

## 10. Exporting Blueprints & Handover Assets

Click the **Export** menu to download the project in your format of choice:
- **Project Handover ZIP:** Complete bundle containing source code, SQL DDL schemas, documentation, and Dockerfiles.
- **Executive PDF Report:** Beautiful, printable multi-page architecture specification document.
- **DOCX Technical Manual:** Editable Word document for formal corporate RFP submissions.
- **Figma Design Tokens:** JSON design token dictionary ready for import into Figma.

---

## 11. Mobile Experience & Android App

- **Responsive Web (PWA):** On any mobile device, open the web app to enjoy touch-optimized navigation, bottom action bars, and swipe gestures.
- **Install PWA:** Tap "Add to Home Screen" in mobile Chrome or Safari for offline-capable native-like experience.
- **Android APK:** The mobile repository includes an Android Capacitor project that can be compiled to a native `.apk` using Android Studio or Gradle.
