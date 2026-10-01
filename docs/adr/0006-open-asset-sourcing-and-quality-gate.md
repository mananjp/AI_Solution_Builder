# ADR 0006: Open Asset Sourcing, Proactive Clarification & Quality Gate

- **Status**: Accepted
- **Date**: 2026-10-01
- **Feature**: Media Asset Sourcing, Architectural Clarification & Quality Gating
- **Deciders**: Engineering & Architecture Team

---

## Context

Generated applications historically suffered from two major quality flaws:
1. **Broken or Missing Imagery**: Applications contained broken image links or generic grey placeholder boxes, destroying the visual appeal of consumer-facing products (such as food menus, retail products, or hero banners).
2. **Ambiguity & Under-Specified Requirements**: Vague prompts (e.g. "make an app for my store") forced LLMs to guess data storage, authentication, and core functionality, resulting in disappointing toy apps.
3. **Packaging Defective Code**: Minor syntax errors, missing exports, or uninstalled dependencies were frequently packaged into final ZIPs, leaving the user with broken projects.

---

## Decision

We introduced a triple-pillar quality guarantee:

1. **Autonomous Open-License Asset Sourcing (`asset_sourcing.py`)**:
   - Queries Wikimedia Commons, Openverse, and Unsplash/Picsum APIs for domain-relevant high-resolution photography matching entity seed data (e.g. vanilla ice cream scoops, chocolate sundaes).
   - Generates a mandatory `CREDITS.json` file attributing creators, sources, and Creative Commons / Public Domain license details.
   - Updates mock records and product cards with valid image URLs.

2. **Proactive Architectural Clarification (`clarification.py` + `ClarificationPanel.tsx`)**:
   - `detect_value_gaps` analyzes user intent to identify ambiguous architectural decisions (e.g. persistence type, authentication necessity, monetization, product taxonomy).
   - Emits structured `clarification_needed` events over SSE and exposes `POST /api/v1/opencode/chat/clarify`.
   - The frontend renders an interactive `ClarificationPanel` allowing users to make one-click alignments or proceed with intelligent defaults.

3. **Strict Quality Gate (`verify_mvp_quality`)**:
   - Controlled via the `MVP_QUALITY_GATE` setting in `backend/app/core/config.py`.
   - Inspects generated code for AST syntax integrity, critical route existence, valid `package.json`, and presence of real seed data.
   - If enabled and quality thresholds are violated, the pipeline triggers self-healing repairs before final packaging.

---

## Consequences

### Positive
- Fully working, visually stunning MVPs with real photos, realistic seed items, and legal license attribution.
- Eliminates user frustration from vague prompt mismatches by offering instant multi-choice alignment before heavy generation.
- Prevents broken code from being packaged and served.

### Limitations & Trade-offs
- Network access to open asset APIs is required during build; robust fallback placeholders are utilized if external media servers timeout.
