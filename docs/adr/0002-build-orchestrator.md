# ADR 0002: Unified Build Orchestrator & Multi-Engine Pipeline

- **Status**: Accepted
- **Date**: 2026-10-01
- **Feature**: Build Pipeline Architecture & Engine Unification
- **Deciders**: Engineering & Architecture Team

---

## Context

Prior to this architecture, MVP generation was fragmented across disconnected execution paths:
1. `mvp_builder.py` performed direct synthesis with ad-hoc template copying and scattered validation logic.
2. `opencode_chat.py` had duplicate build and progression steps for chat-initiated MVP generation.
3. Multiple stages (theming, visual asset fetching, validation, repair, packaging) were either missing or executed out of order, leading to fragile builds and hardcoded placeholder templates.
4. If a build failed or needed healing, the error feedback loop did not unify artifact creation, credit handling, and progress emission.

A cohesive, observable pipeline was required that could run either via the local integrated synthesizer or the remote OpenCode sidecar, while guaranteeing consistent step progression and artifact hygiene.

---

## Decision

We introduced `backend/app/services/build_orchestrator.py` featuring:

1. **`BuildContext` Envelope**:
   - Encapsulates solution identity, workspace paths, build numbering, resolved `AppSpec`, prompt requirements, and user customization flags.
   - Provides a structured `emit_progress(phase, percent, message)` callback that normalizes progress reporting across both SSE streams and async background workers.

2. **Standardized 9-Stage Pipeline (`run_build_pipeline`)**:
   - **Phase 1: Spec Resolution (`resolving_spec`)**: Validates or dynamically infers `AppSpec` v2 from solution artifacts or user prompt.
   - **Phase 2: Domain Theming (`theming`)**: Applies industry-aligned color tokens, typography, and dark/light modes.
   - **Phase 3: Visual Sourcing (`sourcing_assets`)**: Fetches authentic open-license imagery and generates `CREDITS.json`.
   - **Phase 4: Non-Destructive Codegen (`generating_code`)**: Emits models, routers, and pages, respecting existing user modifications.
   - **Phase 5: Synthesis (`synthesizing`)**: Coordinates the primary code generation through the active engine (sidecar or synthesizer).
   - **Phase 6: Quality Verification (`verifying`)**: Runs structural syntax checks, import linters, and quality heuristics.
   - **Phase 7: Self-Healing & Repair (`repairing`)**: Runs AST/LLM repair passes if syntax or component errors are detected.
   - **Phase 8: Packaging (`packaging`)**: Produces a clean deployment ZIP archive and indexes build metadata.
   - **Phase 9: Finalization (`completed`)**: Records build stats, file counts, and unlocks build concurrency tokens.

3. **Engine Decoupling**:
   - Both `mvp_builder.run_build` and `opencode_chat.py` delegate their core build operations to `run_build_pipeline`, guaranteeing identical quality regardless of entry point.

---

## Consequences

### Positive
- **Single Source of Truth**: Eliminates divergent build behavior between quick-build and chat-prompted builds.
- **Resilience**: Every build undergoes automatic verification, syntax inspection, and self-repair before packaging.
- **Traceability**: Unified milestone reporting ensures frontend progress meters never freeze or skip phases.

### Limitations & Trade-offs
- Pipeline execution time scales slightly with asset sourcing and deep verification, though caching and fallback mechanisms mitigate latency.
