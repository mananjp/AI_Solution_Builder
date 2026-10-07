"""
AI Solution Builder — Unified Build Orchestrator (Ticket #18)

Single entry-point for all MVP code generation, theming, asset sourcing,
scaffolding, OpenCode synthesis, verification, and quality gating.
Wires both the REST MVP builder and the streaming chat builder into a unified,
consistent, high-quality pipeline.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.services import mvp_builder as builder
from app.services import spec_codegen
from app.services.app_spec import AppSpec, fallback_app_spec, generate_app_spec
from app.services.asset_sourcing import source_assets_for_spec, wire_generated_visuals
from app.services.mvp_verifier import VerificationError, verify_and_repair, verify_mvp_quality
from app.services.theme_engine import apply_theme, classify_vertical, fallback_theme

logger = logging.getLogger(__name__)


@dataclass
class BuildContext:
    solution_id: UUID
    build_number: int
    workspace_dir: Path
    target_dir: str
    ai_state: dict[str, Any]
    user_prompt: str = ""
    uploaded_context: str = ""
    conversation_history: list[dict[str, Any]] | None = None
    spec: AppSpec | None = None
    session_id: str | None = None
    sidecar_url: str | None = None
    progress_cb: Callable[[str, int, int, str], Awaitable[None]] | None = None
    check_npm: bool = False
    quality_report: dict[str, Any] | None = None
    image_artifacts: list[Any] = field(default_factory=list)
    allow_offline: bool = False


async def run_build_pipeline(ctx: BuildContext) -> dict[str, Any]:
    """Execute the full end-to-end build pipeline."""

    async def _notify(phase: str, step_idx: int, pct: int, msg: str) -> None:
        if ctx.progress_cb:
            await ctx.progress_cb(phase, step_idx, pct, msg)

    # ── Phase 0: Architecture & Spec Resolution ──
    await _notify("analyzing", 0, 15, "Synthesizing domain architecture & specifications...")
    spec = ctx.spec
    if spec is None:
        spec_data = ctx.ai_state.get("app_spec")
        if isinstance(spec_data, dict):
            try:
                spec = AppSpec.model_validate(spec_data)
            except Exception:
                spec = None

    effective_prompt = (
        ctx.user_prompt
        or ctx.ai_state.get("user_message", "")
        or ctx.ai_state.get("business_description", "")
        or "Custom Application"
    )

    if spec is None:
        try:
            spec = await generate_app_spec(
                ctx.ai_state,
                effective_prompt,
                uploaded_context=ctx.uploaded_context,
                conversation_history=ctx.conversation_history,
            )
        except Exception as exc:
            logger.warning("generate_app_spec fallback triggered (%s)", exc)
            spec = fallback_app_spec(
                ctx.ai_state,
                effective_prompt,
                uploaded_context=ctx.uploaded_context,
                conversation_history=ctx.conversation_history,
            )

    ctx.spec = spec
    ctx.ai_state["app_spec"] = spec.model_dump()

    # ── Phase 1: Theme & Visual Asset Sourcing ──
    await _notify("designing", 1, 35, f"Styling tailored design tokens for {spec.app_name}...")
    try:
        # Determine theme
        if not getattr(spec, "theme", None):
            vertical = classify_vertical(
                spec=spec, text=f"{spec.app_name} {spec.one_liner} {spec.core_value}"
            )
            theme_spec = fallback_theme(vertical)
            spec.theme = theme_spec
            ctx.ai_state["app_spec"] = spec.model_dump()
    except Exception as exc:
        logger.warning("Theme application warning (%s)", exc)

    # Source visual assets
    try:
        assets = await source_assets_for_spec(spec, count=4)
        wire_generated_visuals(spec, ctx.workspace_dir, assets)
    except Exception as exc:
        logger.warning("Asset sourcing warning (%s)", exc)

    # ── Phase 2: Scaffolding & Non-Destructive Codegen ──
    await _notify("scaffolding", 2, 50, "Scaffolding full-stack application workspace...")
    modules = [e.name for e in spec.entities]
    builder.scaffold_build(
        ctx.workspace_dir,
        app_title=spec.app_name,
        inject_modules=modules,
        ai_state=ctx.ai_state,
        spec=spec,
    )

    # Write deterministic files and non-destructive pages
    spec_codegen.write_generated(ctx.workspace_dir, spec)

    # Apply CSS design tokens to frontend
    fe_dir = ctx.workspace_dir / "frontend"
    if fe_dir.exists() and spec.theme is not None:
        try:
            apply_theme(fe_dir, spec.theme)
        except Exception as exc:
            logger.warning("apply_theme error (%s)", exc)

    # ── Phase 3: Synthesis (OpenCode Sidecar or Deterministic Stubs) ──
    await _notify("coding", 3, 70, "Synthesizing domain logic, APIs, and responsive UI...")
    sidecar_ok = await builder.health() if not ctx.allow_offline else False
    session_id = "auto-synthesized"
    sidecar_url = None

    if sidecar_ok:
        try:
            session_id = await builder.create_session(
                f"MVP Build - {spec.app_name}", seed=str(ctx.solution_id)
            )
            sidecar_url = builder._sidecar_base_by_session.get(session_id)
            prompt = builder.build_mvp_prompt(spec, ctx.target_dir, app_title=spec.app_name)

            # Active workspace monitor so progress never looks stuck at 70% while LLM writes code
            stop_monitor = asyncio.Event()

            async def _monitor_synthesis() -> None:
                pct = 70
                while not stop_monitor.is_set():
                    try:
                        await asyncio.sleep(3.5)
                        if stop_monitor.is_set():
                            break
                        n_files = len(builder.list_build_files(ctx.workspace_dir))
                        if pct < 84:
                            pct += 1
                        msg = f"Synthesizing full-stack code ({n_files} files generated)..."
                        await _notify("coding", 3, pct, msg)
                    except Exception:
                        pass

            monitor_task = asyncio.create_task(_monitor_synthesis())
            try:
                await builder.send_build_prompt(session_id, prompt, seed=str(ctx.solution_id))
            finally:
                stop_monitor.set()
                monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await monitor_task
        except Exception as exc:
            if session_id and session_id != "auto-synthesized":
                with contextlib.suppress(Exception):
                    await builder.abort_session(session_id, seed=str(ctx.solution_id))
            if isinstance(exc, builder.MVPBuilderError) or not ctx.allow_offline:
                raise
            logger.warning(
                "Sidecar synthesis error (%s); falling back to deterministic synthesis", exc
            )

    # ── Phase 4: Verification & Quality Gate ──
    await _notify("verifying", 4, 86, "Verifying code integrity, type checks & acceptance tests...")
    verification: dict[str, Any] = {}
    try:
        verification = await verify_and_repair(
            ctx.workspace_dir,
            session_id=session_id if sidecar_ok else None,
            target_dir=ctx.target_dir,
            send_prompt_fn=lambda s, t: builder.send_build_prompt(s, t, seed=str(ctx.solution_id)),
            check_npm=ctx.check_npm,
        )
    except VerificationError as v_err:
        if sidecar_ok:
            raise v_err
        logger.warning("Offline build verification note: %s", v_err)

    # Fake-implementation audit: catches apps that only look alive
    # (constant responses, volatile storage, foreign sample data, screens
    # that never talk to the server). Blockers trigger a repair turn.
    from app.services import fake_detector

    audit = fake_detector.audit_build(ctx.workspace_dir, spec)
    fake_detector.write_report(ctx.workspace_dir, audit)
    audit_blockers = fake_detector.blockers(audit)
    if audit_blockers and sidecar_ok and session_id != "auto-synthesized":
        await _notify("repairing", 4, 90, fake_detector.plain_summary(audit))
        try:
            await builder.send_build_prompt(
                session_id,
                fake_detector.repair_brief(audit),
                seed=str(ctx.solution_id),
            )
            audit = fake_detector.audit_build(ctx.workspace_dir, spec)
            fake_detector.write_report(ctx.workspace_dir, audit)
            audit_blockers = fake_detector.blockers(audit)
        except Exception as exc:
            logger.warning("Fake-implementation repair turn failed: %s", exc)
    if audit_blockers:
        logger.warning(
            "Build %s has %d fake-implementation blocker(s)",
            ctx.build_number,
            len(audit_blockers),
        )

    # Quality gate check
    quality_issues = verify_mvp_quality(ctx.workspace_dir, spec)
    if quality_issues:
        logger.info("Quality gate audit: %d note(s): %s", len(quality_issues), quality_issues)
        if getattr(settings, "MVP_QUALITY_GATE", False):
            raise VerificationError("MVP Quality Gate failed: " + "; ".join(quality_issues[:3]))

    # ── Phase 5: Packaging ──
    await _notify("packaging", 5, 95, "Packaging deliverable workspace artifact...")
    files = builder.list_build_files(ctx.workspace_dir)
    tests = verification.get("tests", {})

    return {
        "session_id": session_id,
        "sidecar_url": sidecar_url,
        "local_dir": str(ctx.workspace_dir),
        "file_count": len(files),
        "files": builder.relative_paths(ctx.workspace_dir),
        "app_spec": spec.model_dump(),
        "quality": {
            "tests_passed": int(tests.get("passed", 0)),
            "tests_failed": int(tests.get("failed", 0)),
            "repair_turns": int(verification.get("repair_turns", 0)),
            "actions": [a.name for a in spec.actions],
            "quality_gate": (
                "failed"
                if audit_blockers
                else ("passed" if not quality_issues else "warned")
            ),
            "audit_blockers": [f.as_dict() for f in audit_blockers],
            "plain_summary": fake_detector.plain_summary(audit),
        },
    }
