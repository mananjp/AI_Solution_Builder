# ADR 0004: Opt-In Analytics & Dependency Decoupling

- **Status**: Accepted
- **Date**: 2026-10-01
- **Feature**: Analytics Modularization & LOCKED_FILES Decoupling
- **Deciders**: Engineering & Architecture Team

---

## Context

Previously, `backend/routers_analytics.py` was unconditionally listed in `LOCKED_FILES` within `spec_codegen.py`. This enforced that every generated MVP—even simple static landing pages, portfolios, or minimalist CRUD utilities—included analytics endpoints and mandatory frontend chart libraries (`recharts`, `lucide-react`).

This caused several issues:
1. Bloated bundle sizes and slower compilation times on simple apps.
2. Incompatible dependencies and unnecessary database overhead when tracking metrics was not requested.
3. Verification failures when an application chose not to generate analytics routes but `LOCKED_FILES` mandated their presence.

---

## Decision

We decoupled analytics into an explicit **opt-in module**:

1. **Decoupled from `LOCKED_FILES`**:
   - Removed `backend/routers_analytics.py` from the static `LOCKED_FILES` list in `spec_codegen.py`.
   - Core immutable system files remain strictly locked (e.g. `backend/database.py`, `backend/main.py`), but domain modules are conditionally orchestrated.

2. **Gated Generation**:
   - `spec.analytics.enabled` explicitly governs whether:
     - `backend/routers_analytics.py` is synthesized and registered in `main.py`.
     - Frontend route `/api/v1/analytics/summary` is generated.
     - `recharts` is added to the generated `package.json` dependencies.
   - For applications with `analytics.enabled = False`, lightweight metric stubs or no charting libraries are emitted, minimizing bundle weight.

---

## Consequences

### Positive
- Smaller, faster frontend bundles for lightweight applications.
- No build breakages due to missing analytics routes when analytics were not requested.
- Clean architectural separation of operational concerns.

### Limitations & Trade-offs
- Applications needing retrofitted analytics after initial creation must update their `AppSpec.analytics.enabled` flag and trigger a delta build.
