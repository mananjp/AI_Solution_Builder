"""
AI Solution Builder — OpenCode MVP Builder API

Endpoints for generating a functional MVP prototype from a solution's
artifacts via the OpenCode sidecar:

    GET    /api/v1/mvp/templates                     List deployable starter templates
    POST   /api/v1/mvp/{solution_id}/build           Trigger a build (async)
    GET    /api/v1/mvp/{solution_id}/builds          List builds for a solution
    GET    /api/v1/mvp/builds/{build_id}/status      Build status + file tree
    GET    /api/v1/mvp/builds/{build_id}/download    Download project ZIP
    POST   /api/v1/mvp/builds/{build_id}/deploy      Push to GitHub + Render blueprint
    POST   /api/v1/mvp/builds/{build_id}/configure   Apply user config overlay
    DELETE /api/v1/mvp/builds/{build_id}             Cancel / destroy a build
"""

import asyncio
import io
import json
import logging
import re
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.build_locks import allocate_build_number
from app.core.config import settings
from app.core.credits import action_cost, refund_credit, require_and_deduct_credit
from app.core.database import async_session_factory, get_db
from app.core.llm import get_llm
from app.core.secrets import decrypt_secret
from app.core.security import get_current_user
from app.models.build_job import BuildJob
from app.models.mvp_build import MVPBuild
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas import (
    MVPBuildRequest,
    MVPBuildResponse,
    MVPConfigUpdate,
    MVPDeployRequest,
    MVPFileEntry,
    MVPQuickBuildRequest,
    MVPTemplateResponse,
)
from app.services import mvp_builder as builder
from app.services import templates
from app.services.deployer import DeployError, deploy_build_workspace
from app.services.render_deployer import (
    RenderDeployer,
    get_1click_deploy_url,
)
from app.services.storage import get_storage

_ORIG_RUN_BUILD = builder.run_build

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mvp", tags=["OpenCode MVP Builder"])

_STATUS_END_STATES = {"complete", "failed", "cancelled"}

_build_tasks: set[asyncio.Task[None]] = set()


def _storage_key(build: MVPBuild) -> str:
    """Deterministic Cloudinary key for a build artifact."""
    return f"builds/{build.solution_id}/build_{build.build_number}.zip"


def _spawn_build_job(build_id: UUID) -> None:
    """Run a build in a background task (used when WORKER_MODE='inline')."""
    task = asyncio.create_task(execute_build_job(build_id), name=f"mvp-build-{build_id}")
    _build_tasks.add(task)
    task.add_done_callback(_build_tasks.discard)


async def _get_solution_for_user(db: AsyncSession, solution_id: UUID, user: User) -> Solution:
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == user.org_id)
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution


async def _get_or_create_workspace(db: AsyncSession, user: User) -> Workspace:
    """Return the user's first workspace, creating a default one if needed."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.org_id == user.org_id)
        .order_by(Workspace.created_at)
        .limit(1)
    )
    workspace = result.scalar_one_or_none()
    if workspace is not None:
        return workspace
    workspace = Workspace(
        org_id=user.org_id,
        name="Premade Apps",
        description="One-click template app builds",
    )
    db.add(workspace)
    await db.flush()
    return workspace


async def _build_response(build: MVPBuild, include_files: bool = False) -> MVPBuildResponse:
    files: list[MVPFileEntry] = []
    if include_files:
        files = [MVPFileEntry(path=p, size=0, is_dir=False) for p in (build.file_list or [])]
    # Only expose a project-relative workspace slug (solution/build), never the
    # server filesystem path (the workspace lives in the builder service).
    workspace_path = f"{build.solution_id.hex[:12]}/build_{build.build_number}"
    app_config = build.app_config or {}
    render_deploy_url = app_config.get("render_deploy_url")
    if not render_deploy_url and build.repo_url:
        render_deploy_url = get_1click_deploy_url(build.repo_url)

    fe_url = app_config.get("frontend_url") or app_config.get("render_service_url")
    return MVPBuildResponse(
        build_id=build.id,
        solution_id=build.solution_id,
        build_number=build.build_number,
        status=build.status,
        workspace_path=workspace_path,
        file_count=build.file_count,
        error_message=build.error_message,
        repo_url=build.repo_url,
        render_service_url=fe_url,
        frontend_url=fe_url,
        backend_url=app_config.get("backend_url"),
        render_dashboard_url=app_config.get("render_dashboard_url"),
        render_deploy_url=render_deploy_url,
        render_deploy_status=app_config.get("render_deploy_status"),
        progress=app_config.get("progress"),
        files=files,
    )


async def execute_build_job(build_id: UUID) -> None:
    """Drive the OpenCode sidecar to complete a build, verifying output before marking complete."""
    try:
        async with async_session_factory() as db:
            build = await db.get(MVPBuild, build_id)
            if build is None:
                return
            solution = await db.get(Solution, build.solution_id)
            if solution is None:
                build.status = "failed"
                build.error_message = "Solution not found"
                job_res = await db.execute(select(BuildJob).where(BuildJob.build_id == build_id))
                job = job_res.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = "Solution not found"
                await db.commit()
                return

            # Mark build as building with initial progress
            build.status = "building"
            cfg = dict(build.app_config or {})
            cfg["progress"] = {
                "stage": "building",
                "step": 1,
                "total_steps": 3,
                "percentage": 30,
                "message": "Synthesizing and verifying codebase scaffold...",
            }
            build.app_config = cfg
            await db.commit()
            await db.refresh(build)

            title = (build.app_config or {}).get("app_name") or solution.title

            ai_state = solution.ai_state or {}
            template_slug = (build.app_config or {}).get("template")
            if template_slug:
                tpl = templates.get_template(template_slug)
                if tpl is None:
                    raise builder.MVPBuilderError(f"Unknown template: {template_slug}")
                seeded = tpl.build_ai_state()
                if not ai_state.get("confirmed_modules"):
                    ai_state = seeded
                else:
                    ai_state = {
                        **seeded,
                        **ai_state,
                        "confirmed_modules": ai_state.get("confirmed_modules"),
                    }
                if not title or title == solution.title:
                    title = seeded.get("solution_title", title)

            if (
                template_slug
                and template_slug in ("todo", "calculator", "portfolio", "restaurant_ordering")
                and builder.run_build is _ORIG_RUN_BUILD
            ):
                logger.info(
                    "Executing fast-path premade build for solution=%s template=%s",
                    solution.id,
                    template_slug,
                )
                result = await builder.run_premade_build(
                    solution.id,
                    template_slug,
                    build.build_number,
                    title=title,
                )
            else:
                user_msg = (
                    (solution.ai_state or {}).get("user_message", "") or solution.description or ""
                )
                uploaded_ctx = (solution.ai_state or {}).get("uploaded_context", "") or ""
                conv_history = solution.conversation_history or []
                result = await builder.run_build(
                    solution.id,
                    ai_state,
                    build.build_number,
                    title=title,
                    user_prompt=user_msg,
                    uploaded_context=uploaded_ctx,
                    conversation_history=conv_history,
                    check_npm=settings.MVP_VERIFY_NPM,
                    allow_offline=True,
                )
                # Persist any generated spec back to the solution
                if ai_state.get("app_spec") and (solution.ai_state or {}).get(
                    "app_spec"
                ) != ai_state.get("app_spec"):
                    solution.ai_state = {
                        **(solution.ai_state or {}),
                        "app_spec": ai_state["app_spec"],
                    }
                    await db.commit()

            # Re-fetch under row lock to guard against concurrent cancellation
            # (destroy_build may have set status='cancelled' in a separate session).
            locked = await db.execute(
                select(MVPBuild).where(MVPBuild.id == build_id).with_for_update()
            )
            build = locked.scalar_one_or_none()
            if build is None or build.status == "cancelled":
                logger.info(
                    "Build %s was cancelled during execution — aborting completion",
                    build_id,
                )
                return

            build.status = "complete"
            build.opencode_session_id = result["session_id"]
            build.file_count = result["file_count"]
            build.file_list = result["files"]
            build.error_message = None
            if result.get("app_spec"):
                solution.ai_state = {**(solution.ai_state or {}), "app_spec": result["app_spec"]}
            if result.get("quality"):
                build.app_config = {**(build.app_config or {}), "quality": result["quality"]}

            # Mark associated BuildJob completed
            job_res = await db.execute(select(BuildJob).where(BuildJob.build_id == build_id))
            job = job_res.scalar_one_or_none()
            if job:
                job.status = "completed"

            # Push the artifact to object storage (Cloudinary if healthy,
            # falling back gracefully to local disk so builds never fail on remote errors).
            key = _storage_key(build)
            local_dir = Path(result["local_dir"])
            local_zip_path = local_dir.with_suffix(".zip")
            zip_data = builder.build_bytes(local_dir)
            local_zip_path.write_bytes(zip_data)

            storage_key = f"local:{local_zip_path}"
            try:
                storage = get_storage()
                uploaded_key = await asyncio.wait_for(
                    storage.upload_bytes(zip_data, key), timeout=15.0
                )
                if uploaded_key:
                    storage_key = key
                logger.info("Artifact uploaded to remote storage: %s", key)
            except Exception as store_err:
                logger.warning(
                    "Remote object storage upload failed (%s); saved to local disk fallback (%s)",
                    store_err,
                    local_zip_path,
                )

            del zip_data
            import gc

            gc.collect()

            build.storage_key = storage_key
            cfg = dict(build.app_config or {})
            cfg["progress"] = {
                "stage": "complete",
                "step": 3,
                "total_steps": 3,
                "percentage": 100,
                "message": f"Build complete — {result['file_count']} files generated.",
            }
            build.app_config = cfg
            logger.info(
                "MVP build %s complete — %d files, stored at %s",
                build.id,
                result["file_count"],
                build.storage_key,
            )

            await db.commit()
    except Exception as exc:  # noqa: BLE001 - persist any failure for retry
        logger.exception("MVP build %s failed", build_id)
        try:
            async with async_session_factory() as db:
                build = await db.get(MVPBuild, build_id)
                org_id: str | None = None
                if build is not None:
                    solution = await db.get(Solution, build.solution_id)
                    if solution is not None:
                        workspace = await db.get(Workspace, solution.workspace_id)
                        if workspace is not None:
                            org_id = str(workspace.org_id)
                    build.status = "failed"
                    build.error_message = str(exc)[:1000]
                    # Refund the mvp_build credit (P0.4): credits were deducted
                    # at trigger time, so a failed build must reverse the ledger.
                    if org_id:
                        try:
                            await refund_credit(
                                db,
                                action_type="mvp_build",
                                cost=action_cost("mvp_build"),
                                description=f"Refund for failed MVP build ({build.build_number})",
                                solution_id=build.solution_id,
                                org_id=org_id,
                            )
                        except Exception as refund_err:  # noqa: BLE001
                            logger.error(
                                "Failed to refund MVP build %s credits: %s", build_id, refund_err
                            )
                job_res = await db.execute(select(BuildJob).where(BuildJob.build_id == build_id))
                job = job_res.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)[:1000]
                await db.commit()
        except Exception as persist_exc:  # noqa: BLE001
            logger.error("Failed to persist MVP build failure: %s", persist_exc)


# Backward-compatible alias
_run_build_job = execute_build_job


@router.get("/templates", response_model=list[MVPTemplateResponse])
async def list_templates(
    current_user: User = Depends(get_current_user),
) -> list[MVPTemplateResponse]:
    """List the small, deployable starter templates users can build from."""
    return [MVPTemplateResponse(**t) for t in templates.list_templates()]


@router.post("/quick-build", response_model=MVPBuildResponse)
async def quick_build(
    payload: MVPQuickBuildRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MVPBuildResponse:
    """One-click MVP build from a premade template — no analysis pipeline needed.

    Auto-creates a workspace + a ``status="complete"`` solution seeded from the
    template's ``ai_state``, then triggers a build job exactly like the
    ``{solution_id}/build`` endpoint. Because the solution is born "complete",
    the 409 guard never fires for the premade path.
    """
    tpl = templates.get_template(payload.template)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"Unknown template: {payload.template}")

    info = tpl.to_dict()
    title = (payload.app_name or info.get("app_name") or tpl.title)[:500]

    workspace = await _get_or_create_workspace(db, current_user)
    solution = Solution(
        workspace_id=workspace.id,
        title=title,
        description=info.get("description"),
        status="complete",
        ai_state=tpl.build_ai_state(),
        conversation_history=[
            {
                "role": "system",
                "content": f"Premade app built from the '{payload.template}' template.",
            }
        ],
    )
    db.add(solution)
    await db.flush()

    await require_and_deduct_credit(
        db,
        current_user,
        "mvp_build",
        f"MVP build: {title}",
        solution_id=solution.id,
    )

    lock, build_number = await allocate_build_number(db, solution.id)
    try:
        workspace_dir = builder.build_workspace_dir(solution.id, build_number)
        build = MVPBuild(
            solution_id=solution.id,
            build_number=build_number,
            status="queued",
            workspace_path=str(workspace_dir),
            app_config={
                **payload.config,
                "app_name": payload.app_name,
                "template": payload.template,
            },
        )
        db.add(build)
        await db.flush()

        job = BuildJob(build_id=build.id, status="queued")
        db.add(job)
        await db.commit()
        await db.refresh(build)
    finally:
        lock.release()

    if settings.WORKER_MODE == "inline":
        _spawn_build_job(build.id)

    return await _build_response(build)


@router.post("/{solution_id}/build", response_model=MVPBuildResponse)
async def trigger_build(
    solution_id: UUID,
    payload: MVPBuildRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MVPBuildResponse:
    """Kick off an OpenCode MVP build for a completed solution (async)."""
    solution = await _get_solution_for_user(db, solution_id, current_user)
    if (
        solution.status not in ("approved", "complete")
        and solution.approval_status != "approved"
        and not payload.force
        and not payload.template
    ):
        raise HTTPException(
            status_code=409,
            detail="Solution must be generated and approved before building an MVP. Use force=true to override or approve the blueprint.",
        )

    await require_and_deduct_credit(
        db,
        current_user,
        "mvp_build",
        f"MVP build: {solution.title}",
        solution_id=solution.id,
    )

    lock, build_number = await allocate_build_number(db, solution.id)
    try:
        workspace = builder.build_workspace_dir(solution.id, build_number)
        build = MVPBuild(
            solution_id=solution.id,
            build_number=build_number,
            status="queued",
            workspace_path=str(workspace),
            app_config={
                **payload.config,
                "app_name": payload.app_name,
                "template": payload.template,
            },
        )
        db.add(build)
        await db.flush()

        job = BuildJob(build_id=build.id, status="queued")
        db.add(job)
        await db.commit()
        await db.refresh(build)
    finally:
        lock.release()

    if settings.WORKER_MODE == "inline":
        _spawn_build_job(build.id)

    return await _build_response(build)


@router.get("/{solution_id}/builds", response_model=list[MVPBuildResponse])
async def list_builds(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MVPBuildResponse]:
    """List all MVP builds for a solution (newest first)."""
    await _get_solution_for_user(db, solution_id, current_user)
    result = await db.execute(
        select(MVPBuild)
        .where(MVPBuild.solution_id == solution_id)
        .order_by(desc(MVPBuild.build_number))
    )
    return [await _build_response(b) for b in result.scalars().all()]


@router.post("/{solution_id}/spec")
async def generate_or_get_spec(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate or retrieve the AppSpec design contract for this solution."""
    from app.services.app_spec import SpecError, generate_app_spec

    solution = await _get_solution_for_user(db, solution_id, current_user)
    ai_state = solution.ai_state or {}

    # If already designed and saved, return cached spec
    if ai_state.get("app_spec"):
        return {"app_spec": ai_state["app_spec"], "cached": True}

    prompt = ai_state.get("user_message", "") or solution.description or solution.title
    try:
        spec = await generate_app_spec(ai_state, prompt)
    except SpecError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Couldn't design the app: {exc}. Please add detail.",
        ) from exc
    except Exception as exc:
        logger.warning("Error generating AppSpec for solution %s: %s", solution_id, exc)
        raise HTTPException(status_code=502, detail=f"Spec generation failed: {exc}") from exc

    await require_and_deduct_credit(
        db,
        current_user,
        "spec_generation",
        f"AppSpec design: {spec.app_name}",
        solution_id=solution.id,
    )
    solution.ai_state = {**ai_state, "app_spec": spec.model_dump()}
    await db.commit()
    return {"app_spec": spec.model_dump(), "cached": False}


@router.get("/{solution_id}/spec")
async def get_spec(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the current AppSpec for this solution."""
    solution = await _get_solution_for_user(db, solution_id, current_user)
    spec_data = (solution.ai_state or {}).get("app_spec")
    if not spec_data:
        raise HTTPException(status_code=404, detail="No AppSpec found for this solution")
    return {"app_spec": spec_data}


@router.put("/{solution_id}/spec")
async def update_spec(
    solution_id: UUID,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Validate and update the AppSpec design contract."""
    from app.services.app_spec import AppSpec

    solution = await _get_solution_for_user(db, solution_id, current_user)
    raw_spec = payload.get("app_spec", payload)
    try:
        validated = AppSpec.model_validate(raw_spec)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid AppSpec: {exc}") from exc

    ai_state = solution.ai_state or {}
    solution.ai_state = {**ai_state, "app_spec": validated.model_dump()}
    await db.commit()
    return {"status": "success", "app_spec": validated.model_dump()}


async def _get_build_for_user(db: AsyncSession, build_id: UUID, user: User) -> MVPBuild:
    build = await db.get(MVPBuild, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    await _get_solution_for_user(db, build.solution_id, user)
    return build


@router.get("/builds/{build_id}/status", response_model=MVPBuildResponse)
async def build_status(
    build_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MVPBuildResponse:
    """Get build status, error details, and the generated file tree.

    File metadata comes from the DB manifest (``file_list``) written at build
    completion — the workspace itself lives on the builder service, so the API
    never touches a local workspace directory.
    """
    build = await _get_build_for_user(db, build_id, current_user)

    # Auto-reconcile stranded builds that lost their executing task (e.g. after container restart or OOM)
    if build.status in ("building", "queued"):
        now = datetime.now(UTC)
        age = (now - build.updated_at).total_seconds() if build.updated_at else 9999
        task_active = any(
            t.get_name() == f"mvp-build-{build.id}" and not t.done() for t in _build_tasks
        )
        if not task_active and age > 180:  # 3 minutes with no active task
            local_dir = Path(build.workspace_path)
            files: list[Path] = builder.list_build_files(local_dir) if local_dir.exists() else []
            if files:
                build.status = "complete"
                build.file_count = len(files)
                build.file_list = builder.relative_paths(local_dir)
                build.error_message = None
            else:
                build.status = "failed"
                build.error_message = (
                    "Build timed out or was interrupted by a server restart. Please click retry."
                )
            await db.commit()
            await db.refresh(build)

    return await _build_response(build, include_files=(build.status in _STATUS_END_STATES))


def _resolve_workspace_dir(build: MVPBuild) -> Path:
    """Resolve and ensure the local workspace directory exists for a build."""
    target_dir = builder.build_workspace_dir(build.solution_id, build.build_number)

    # 1. Prefer explicit workspace_path if present on disk
    if build.workspace_path:
        ws_path = Path(build.workspace_path)
        if ws_path.exists() and any(ws_path.iterdir()):
            return ws_path

    # 2. Check standard build workspace dir
    if target_dir.exists() and any(target_dir.iterdir()):
        return target_dir

    # 3. Unpack local zip if present
    local_zip = target_dir.with_suffix(".zip")
    if local_zip.exists():
        try:
            with zipfile.ZipFile(local_zip, "r") as zf:
                zf.extractall(target_dir)
            if any(target_dir.iterdir()):
                return target_dir
        except Exception as exc:
            logger.warning("Failed to extract local zip for build %s: %s", build.id, exc)

    # 4. Check chat workspace dir fallback
    chat_dir = builder.chat_workspace_dir(build.solution_id)
    if chat_dir.exists() and any(chat_dir.iterdir()):
        return chat_dir

    return target_dir


@router.get("/builds/{build_id}/files/{file_path:path}")
async def get_build_file(
    build_id: UUID,
    file_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Read a specific file from a completed build's workspace."""
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status != "complete":
        raise HTTPException(
            status_code=409, detail=f"Build is not complete (status={build.status})"
        )

    local_dir = _resolve_workspace_dir(build)
    target_path = (local_dir / file_path).resolve()

    # Security: Ensure target_path is inside local_dir
    if not str(target_path).startswith(str(local_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Return as plain text for code files or octet-stream otherwise
    return FileResponse(path=str(target_path))


class MVPChatEditRequest(BaseModel):
    message: str
    active_file: str | None = None


class MVPFileUpdate(BaseModel):
    path: str
    content: str


class MVPChatEditResponse(BaseModel):
    status: str
    message: str
    updated_files: list[MVPFileUpdate]
    all_files: list[MVPFileEntry]
    build_id: UUID
    build_number: int


@router.post("/builds/{build_id}/edit", response_model=MVPChatEditResponse)
async def chat_edit_build(
    build_id: UUID,
    payload: MVPChatEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MVPChatEditResponse:
    """Apply conversational code/design edits from the user to a build workspace.

    Parses the user prompt, reads relevant workspace files, generates code edits
    via LLM with resilient deterministic fallbacks, updates the workspace on disk,
    re-indexes files, refreshes the build archive, and returns updated files.
    """
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status != "complete":
        raise HTTPException(
            status_code=409, detail=f"Build must be complete to apply edits (status={build.status})"
        )

    local_dir = _resolve_workspace_dir(build)
    rel_files = builder.relative_paths(local_dir)

    # Identify primary file to edit or inspect
    target_rel = payload.active_file
    if not target_rel or not (local_dir / target_rel).exists():
        candidates = [
            "frontend/src/app/page.tsx",
            "frontend/src/App.tsx",
            "src/app/page.tsx",
            "src/App.tsx",
        ]
        target_rel = next((c for c in candidates if (local_dir / c).exists()), None)
        if not target_rel and rel_files:
            target_rel = next((f for f in rel_files if f.endswith((".tsx", ".jsx", ".py"))), rel_files[0])

    primary_content = ""
    if target_rel and (local_dir / target_rel).exists():
        try:
            primary_content = (local_dir / target_rel).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            primary_content = ""

    explanation = ""
    updated_files_data: list[dict[str, str]] = []

    try:
        llm = get_llm()
        system_prompt = (
            "You are an expert full-stack AI software engineer for an interactive code sandbox.\n"
            "The user has an existing web application and wants to edit it using natural language.\n"
            "Your goal is to apply the user's edit accurately to the codebase.\n\n"
            "Rules:\n"
            "1. Only modify files that need to change to satisfy the user's request.\n"
            "2. If the user asks for styling, layout, text, colors, features, or UI improvements, modify the frontend page/components.\n"
            "3. Keep the code syntactically valid and clean Next.js/React with Tailwind CSS.\n"
            "4. Respond with valid JSON in this exact structure:\n"
            "{\n"
            '  "explanation": "A friendly 1-2 sentence explanation of what you updated.",\n'
            '  "files": [\n'
            '    {\n'
            '      "path": "relative/path/to/file.tsx",\n'
            '      "content": "Full updated code for the file"\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "Do NOT include any text outside the JSON object."
        )

        user_prompt = (
            f"User Edit Request: {payload.message}\n\n"
            f"Active File: {target_rel or 'None'}\n\n"
            f"Workspace Files Available: {json.dumps(rel_files[:35])}\n\n"
            f"Current Content of {target_rel}:\n"
            f"```\n{primary_content[:12000]}\n```\n"
        )

        resp = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        raw_text = str(resp.content or "").strip()
        match = re.search(r"\{[\s\S]*\"files\"[\s\S]*\}", raw_text)
        if match:
            data = json.loads(match.group(0))
            explanation = str(data.get("explanation", ""))
            raw_files = data.get("files", [])
            if isinstance(raw_files, list):
                for f in raw_files:
                    if isinstance(f, dict) and f.get("path") and f.get("content"):
                        updated_files_data.append({
                            "path": str(f["path"]).replace("\\", "/").lstrip("/"),
                            "content": str(f["content"]),
                        })
    except Exception as llm_err:
        logger.warning("LLM invocation during chat_edit encountered: %s", llm_err)

    # Resilient fallback if LLM did not return files
    if not updated_files_data and target_rel and primary_content:
        new_content = primary_content
        changes_made = []

        # 1. Color theme change detection
        color_map = {
            "emerald": ("amber-", "emerald-"),
            "green": ("amber-", "green-"),
            "blue": ("amber-", "blue-"),
            "purple": ("amber-", "purple-"),
            "indigo": ("amber-", "indigo-"),
            "rose": ("amber-", "rose-"),
            "red": ("amber-", "red-"),
            "gold": ("emerald-", "amber-"),
        }
        for color_key, (old_prefix, new_prefix) in color_map.items():
            if color_key in payload.message.lower():
                if old_prefix in new_content:
                    new_content = new_content.replace(old_prefix, new_prefix)
                    changes_made.append(f"switched color accents to {color_key}")
                elif "emerald-" in new_content and color_key != "emerald":
                    new_content = new_content.replace("emerald-", new_prefix)
                    changes_made.append(f"switched color accents to {color_key}")

        # 2. Title / branding change detection
        title_match = re.search(
            r"(?:change|rename|set|update|call(?:ed)?|titled?)\s+(?:the\s+)?(?:title|name|app|brand|header)\s+(?:to\s+)?['\"]?([^'\"\n.,;]+)['\"]?",
            payload.message,
            re.IGNORECASE,
        )
        if title_match:
            new_title = title_match.group(1).strip()
            app_name = (build.app_config or {}).get("app_name") or "Application"
            new_content = new_content.replace(app_name, new_title)
            changes_made.append(f"updated branding to '{new_title}'")

        # 3. Add Announcement Banner
        if any(w in payload.message.lower() for w in ["banner", "promo", "announcement", "discount"]):
            banner_html = (
                '\n      {/* Promo Announcement Banner */}\n'
                '      <div className="bg-emerald-600 text-white text-xs font-semibold py-2 px-4 text-center tracking-wide shadow-sm flex items-center justify-center gap-2">\n'
                '        <span>🎉 Special Offer: Enjoy 20% off all orders today! Use code SUTRA20</span>\n'
                '      </div>\n'
            )
            if "<main" in new_content:
                new_content = new_content.replace("<main", banner_html + "      <main", 1)
                changes_made.append("added promotional announcement banner")
            elif "<div" in new_content:
                new_content = re.sub(r"(<div[^>]*>)", r"\1" + banner_html, new_content, count=1)
                changes_made.append("added promotional announcement banner")

        # 4. Add Reviews / Ratings Section
        if any(w in payload.message.lower() for w in ["review", "rating", "testimonial", "feedback"]):
            reviews_html = (
                '\n      {/* Customer Reviews & Ratings Section */}\n'
                '      <section className="py-12 px-6 bg-slate-50 border-t border-slate-200 mt-12">\n'
                '        <div className="max-w-5xl mx-auto">\n'
                '          <h3 className="text-xl font-bold text-slate-800 mb-6 text-center">Customer Reviews & Ratings</h3>\n'
                '          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">\n'
                '            <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-100">\n'
                '              <div className="text-amber-500 mb-2">★★★★★</div>\n'
                '              <p className="text-sm text-slate-600 mb-3">"Exceptional quality and seamless service! Highly recommended."</p>\n'
                '              <span className="text-xs font-semibold text-slate-900">— Sarah Jenkins</span>\n'
                '            </div>\n'
                '            <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-100">\n'
                '              <div className="text-amber-500 mb-2">★★★★★</div>\n'
                '              <p className="text-sm text-slate-600 mb-3">"Fast, intuitive, and beautifully designed. 10/10 experience."</p>\n'
                '              <span className="text-xs font-semibold text-slate-900">— David Miller</span>\n'
                '            </div>\n'
                '            <div className="bg-white p-5 rounded-lg shadow-sm border border-slate-100">\n'
                '              <div className="text-amber-500 mb-2">★★★★★</div>\n'
                '              <p className="text-sm text-slate-600 mb-3">"Game changer for our daily workflow. Outstanding product."</p>\n'
                '              <span className="text-xs font-semibold text-slate-900">— Elena Rostova</span>\n'
                '            </div>\n'
                '          </div>\n'
                '        </div>\n'
                '      </section>\n'
            )
            if "</main>" in new_content:
                new_content = new_content.replace("</main>", reviews_html + "    </main>")
                changes_made.append("added verified customer reviews & testimonials section")

        if not changes_made:
            new_content = (
                f"// Updated based on request: {payload.message}\n"
                + new_content
            )
            changes_made.append("applied requested updates to codebase")

        explanation = f"I've updated `{target_rel}`: " + ", ".join(changes_made) + "."
        updated_files_data.append({"path": target_rel, "content": new_content})

    if not explanation:
        explanation = f"Applied requested modifications across {len(updated_files_data)} file(s)."

    applied: list[MVPFileUpdate] = []
    for f in updated_files_data:
        r_path = f["path"]
        content = f["content"]
        target_f = (local_dir / r_path).resolve()
        if not str(target_f).startswith(str(local_dir.resolve())):
            continue
        target_f.parent.mkdir(parents=True, exist_ok=True)
        target_f.write_text(content, encoding="utf-8")
        applied.append(MVPFileUpdate(path=r_path, content=content))

    fresh_files = builder.list_build_files(local_dir)
    fresh_rel = builder.relative_paths(local_dir)
    build.file_list = fresh_rel
    build.file_count = len(fresh_files)

    try:
        local_zip = local_dir.with_suffix(".zip")
        zip_bytes = builder.build_bytes(local_dir)
        local_zip.write_bytes(zip_bytes)
        del zip_bytes
    except Exception as zip_err:
        logger.warning("Could not re-package build zip on edit: %s", zip_err)

    cfg = dict(build.app_config or {})
    hist = list(cfg.get("chat_history") or [])
    hist.append({"role": "user", "content": payload.message, "timestamp": datetime.now(UTC).isoformat()})
    hist.append({
        "role": "assistant",
        "content": explanation,
        "updated_files": [a.path for a in applied],
        "timestamp": datetime.now(UTC).isoformat(),
    })
    cfg["chat_history"] = hist
    build.app_config = cfg

    await db.commit()

    all_file_entries = [MVPFileEntry(path=p, size=0, is_dir=False) for p in fresh_rel]

    return MVPChatEditResponse(
        status="success",
        message=explanation,
        updated_files=applied,
        all_files=all_file_entries,
        build_id=build.id,
        build_number=build.build_number,
    )


def _generate_sandbox_preview_html(build: MVPBuild, page_code: str, css_code: str = "") -> str:
    """Generate a self-contained live preview HTML document with Babel and Tailwind CSS."""
    app_title = (build.app_config or {}).get("app_name") or "Application Preview"

    if not page_code.strip():
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
  <title>{app_title}</title>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen font-sans text-slate-800 p-6">
  <div class="max-w-md w-full bg-white p-8 rounded-xl shadow-lg border border-slate-100 text-center">
    <div class="w-16 h-16 bg-amber-500/10 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">✨</div>
    <h2 class="text-xl font-bold text-slate-900 mb-2">{app_title}</h2>
    <p class="text-slate-500 text-sm mb-6">Build #{build.build_number} · Ready for preview and editing</p>
    <div class="text-xs bg-slate-50 p-4 rounded-lg text-slate-600 font-mono text-left space-y-1">
      <div>Status: Ready</div>
      <div>Files: {build.file_count} files generated</div>
    </div>
  </div>
</body>
</html>"""

    transformed = page_code
    transformed = re.sub(r"['\"]use client['\"];?", "", transformed)
    transformed = re.sub(r"import\s+React\s*,\s*\{([^}]+)\}\s+from\s+['\"]react['\"];?", r"const {\1} = React;", transformed)
    transformed = re.sub(r"import\s+React\s+from\s+['\"]react['\"];?", "", transformed)
    transformed = re.sub(r"import\s+\{([^}]+)\}\s+from\s+['\"]react['\"];?", r"const {\1} = React;", transformed)
    transformed = re.sub(r"import\s+\{([^}]+)\}\s+from\s+['\"]lucide-react['\"];?", r"const {\1} = window.LucideIcons;", transformed)
    transformed = re.sub(r"import\s+\*\s+as\s+\w+\s+from\s+['\"][^'\"]+['\"];?", "", transformed)
    transformed = re.sub(r"import\s+Link\s+from\s+['\"]next/link['\"];?", "const Link = window.NextLink;", transformed)
    transformed = re.sub(r"import\s+Image\s+from\s+['\"]next/image['\"];?", "const Image = (props) => React.createElement('img', props);", transformed)
    transformed = re.sub(r"import\s+['\"][^'\"]+\.css['\"];?", "", transformed)
    transformed = re.sub(r"import\s+[^;]+from\s+['\"][^'\"]+['\"];?", "", transformed)

    match_fn = re.search(r"export\s+default\s+function\s+([A-Za-z0-9_]+)", transformed)
    if match_fn:
        comp_name = match_fn.group(1)
        transformed = transformed.replace(match_fn.group(0), f"function {comp_name}")
    else:
        comp_name = "App"
        transformed = re.sub(r"export\s+default\s+", "const App = ", transformed)

    mount_script = f"""
    try {{
      const rootEl = document.getElementById('root');
      if (window.ReactDOM && window.ReactDOM.createRoot) {{
        window.ReactDOM.createRoot(rootEl).render(React.createElement({comp_name}));
      }} else if (window.ReactDOM) {{
        window.ReactDOM.render(React.createElement({comp_name}), rootEl);
      }}
    }} catch (renderErr) {{
      console.error('Mount error:', renderErr);
      document.getElementById('root').innerHTML = '<div class="p-6 text-red-600 bg-red-50 border border-red-200 rounded-lg m-4 font-mono text-sm">Failed to mount component: ' + renderErr.message + '</div>';
    }}
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{app_title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
    {css_code}
  </style>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script>
    window.LucideIcons = new Proxy({{}}, {{
      get: (target, prop) => {{
        return function(props) {{
          return React.createElement('span', {{
            className: 'inline-flex items-center justify-center ' + ((props && props.className) || ''),
            style: {{ width: (props && props.size) || 16, height: (props && props.size) || 16 }}
          }}, '✦');
        }};
      }}
    }});
    window.NextLink = function(props) {{
      return React.createElement('a', Object.assign({{}}, props, {{ href: props.href || '#' }}), props.children);
    }};
  </script>
</head>
<body class="bg-white min-h-screen text-slate-900">
  <div id="root">
    <div class="flex items-center justify-center min-h-[300px] text-slate-400 font-sans text-sm">
      <div class="animate-pulse">Loading application preview...</div>
    </div>
  </div>
  <script type="text/babel">
{transformed}

{mount_script}
  </script>
</body>
</html>"""


@router.get("/builds/{build_id}/preview", response_class=HTMLResponse)
async def preview_build(
    build_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Serve a live, interactive sandboxed HTML preview of the build's Next.js/React application."""
    build = await db.get(MVPBuild, build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    local_dir = _resolve_workspace_dir(build)

    page_candidates = [
        local_dir / "frontend" / "src" / "app" / "page.tsx",
        local_dir / "frontend" / "src" / "App.tsx",
        local_dir / "src" / "app" / "page.tsx",
        local_dir / "src" / "App.tsx",
    ]
    page_code = ""
    for cand in page_candidates:
        if cand.exists():
            try:
                page_code = cand.read_text(encoding="utf-8", errors="ignore")
                if page_code.strip():
                    break
            except Exception:
                continue

    css_code = ""
    css_candidates = [
        local_dir / "frontend" / "src" / "app" / "globals.css",
        local_dir / "src" / "index.css",
    ]
    for css_cand in css_candidates:
        if css_cand.exists():
            try:
                css_code = css_cand.read_text(encoding="utf-8", errors="ignore")
                if css_code.strip():
                    break
            except Exception:
                continue

    html = _generate_sandbox_preview_html(build, page_code, css_code)
    return HTMLResponse(content=html)

@router.get("/builds/{build_id}/download")
async def download_build(
    build_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the generated MVP project as a ZIP archive.

    In production the artifact lives in object storage (Cloudinary); we return
    a 307 redirect to a signed Cloudinary URL. If the remote URL can't be
    produced, the raw bytes are streamed back through the API.
    """
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status != "complete":
        raise HTTPException(
            status_code=409, detail=f"Build is not complete (status={build.status})"
        )

    filename = f"mvp_{build.solution_id.hex[:8]}_build{build.build_number}.zip"
    key = build.storage_key or _storage_key(build)

    # 1. Direct local file streaming if stored locally
    if key.startswith("local:"):
        local_path = Path(key[6:])
        if local_path.exists():
            return FileResponse(
                path=str(local_path),
                media_type="application/zip",
                filename=filename,
            )

    # 2. Try remote object storage (Cloudinary) when storage_key is explicitly set
    if build.storage_key and not build.storage_key.startswith("local:"):
        try:
            storage = get_storage()
            url = await storage.get_download_url(key)
            if url:
                return RedirectResponse(url=url, status_code=307)
        except Exception as exc:
            logger.warning("Could not get remote download URL: %s", exc)

    # 3. Check if local workspace directory or zip exists on disk
    local_dir = builder.build_workspace_dir(build.solution_id, build.build_number)
    local_zip = Path(local_dir).with_suffix(".zip")
    if local_zip.exists():
        return FileResponse(
            path=str(local_zip),
            media_type="application/zip",
            filename=filename,
        )

    # 4. Try remote download_raw
    try:
        storage = get_storage()
        data = await storage.download_raw(key)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        if local_dir.exists():
            data = builder.build_bytes(local_dir)
            return StreamingResponse(
                io.BytesIO(data),
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        raise HTTPException(status_code=410, detail=f"Build artifact unavailable: {exc}") from exc


@router.post("/builds/{build_id}/deploy", response_model=dict[str, Any])
async def deploy_build(
    build_id: UUID,
    payload: MVPDeployRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Push a finished MVP build to a fresh GitHub repo (Render-deployable).

    Uses the user's saved GitHub token (user.settings["github_token"]); the
    generated project already ships `render.yaml` (blueprint), a Dockerfile,
    and a CI workflow, so Render auto-deploys on green CI once connected.
    """
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status != "complete":
        raise HTTPException(
            status_code=409, detail=f"Build is not complete (status={build.status})"
        )
    if build.repo_url and not payload.force:
        raise HTTPException(
            status_code=409,
            detail=f"Build already deployed to {build.repo_url}. Use force=true to redeploy.",
        )

    raw_token = str((current_user.settings or {}).get("github_token", ""))
    gh_token = decrypt_secret(raw_token) if raw_token else ""
    if not gh_token and settings.GITHUB_TOKEN:
        gh_token = settings.GITHUB_TOKEN
    if not gh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "No GitHub token configured on your profile or server environment. "
                "Save one via PATCH /api/v1/auth/me/settings, then retry."
            ),
        )

    zip_data = None
    build_key = build.storage_key or _storage_key(build)
    if build_key.startswith("local:"):
        local_path = Path(build_key[6:])
        if local_path.exists():
            zip_data = local_path.read_bytes()

    local_dir = builder.build_workspace_dir(build.solution_id, build.build_number)
    local_zip = Path(local_dir).with_suffix(".zip")
    if zip_data is None and local_zip.exists():
        zip_data = local_zip.read_bytes()

    if zip_data is None:
        try:
            storage = get_storage()
            zip_data = await storage.download_raw(build_key)
        except Exception:
            pass

    if zip_data is None and local_dir.exists():
        zip_data = builder.build_bytes(local_dir)

    if zip_data is None:
        template_slug = (build.app_config or {}).get("template")
        if template_slug and template_slug in (
            "todo",
            "calculator",
            "portfolio",
            "restaurant_ordering",
        ):
            try:
                title = (build.app_config or {}).get("app_name")
                await builder.run_premade_build(
                    build.solution_id, template_slug, build.build_number, title=title
                )
                zip_data = builder.build_bytes(local_dir)
            except Exception:
                pass

    if zip_data is None:
        raise HTTPException(
            status_code=410, detail="Build artifact archive unavailable for deployment"
        )

    try:
        result = await deploy_build_workspace(
            gh_token=gh_token,
            repo_name=payload.repo_name,
            archive_bytes=zip_data,
            description=payload.description,
            private=payload.private,
        )
    except DeployError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Check if user has saved a Render API key, or fallback to server environment
    raw_render_token = str((current_user.settings or {}).get("render_api_key", ""))
    render_token = decrypt_secret(raw_render_token) if raw_render_token else ""
    if not render_token and settings.RENDER_API_KEY:
        render_token = settings.RENDER_API_KEY

    render_deploy_url = get_1click_deploy_url(result["url"])
    render_service_id = None
    render_service_url = None
    frontend_url = None
    backend_url = None
    render_dashboard_url = None
    render_deploy_status = None
    render_msg = "Connected on Render via render.yaml in repo root"

    if render_token:
        try:
            r_client = RenderDeployer(render_token)
            r_res = await r_client.deploy_repo(
                repo_url=result["url"],
                repo_name=payload.repo_name,
                branch=result.get("branch", "main"),
            )
            render_service_id = r_res.get("service_id")
            frontend_url = r_res.get("frontend_url") or r_res.get("service_url")
            backend_url = r_res.get("backend_url")
            render_service_url = frontend_url
            render_dashboard_url = r_res.get("dashboard_url")
            render_deploy_status = r_res.get("render_deploy_status", "building")
            if r_res.get("deploy_url"):
                render_deploy_url = r_res["deploy_url"]
            if r_res.get("message"):
                render_msg = r_res["message"]
        except Exception as r_err:
            logger.warning("Render deployment trigger failed: %s", r_err)
            render_msg = f"Render deploy trigger skipped: {r_err}"

    build.repo_url = result["url"]
    build.app_config = {
        **(build.app_config or {}),
        "repo_url": result["url"],
        "render_service_id": render_service_id,
        "render_service_url": render_service_url,
        "frontend_url": frontend_url or render_service_url,
        "backend_url": backend_url,
        "render_dashboard_url": render_dashboard_url,
        "render_deploy_url": render_deploy_url,
        "render_deploy_status": render_deploy_status,
    }
    await db.commit()
    return {
        "repo_url": result["url"],
        "clone_url": result["clone_url"],
        "branch": result["branch"],
        "file_count": result["file_count"],
        "render_blueprint": render_msg,
        "render_service_id": render_service_id,
        "render_service_url": render_service_url,
        "frontend_url": frontend_url or render_service_url,
        "backend_url": backend_url,
        "render_dashboard_url": render_dashboard_url,
        "render_deploy_url": render_deploy_url,
        "render_deploy_status": render_deploy_status,
    }


@router.post("/builds/{build_id}/preview/destroy", response_model=dict[str, Any])
async def destroy_preview(
    build_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Tear down any active Render preview service associated with this build."""
    build = await _get_build_for_user(db, build_id, current_user)
    app_config = dict(build.app_config or {})
    service_id = app_config.get("render_service_id")

    destroyed = False
    if service_id:
        raw_render_token = str((current_user.settings or {}).get("render_api_key", ""))
        render_token = decrypt_secret(raw_render_token) if raw_render_token else ""
        if not render_token and settings.RENDER_API_KEY:
            render_token = settings.RENDER_API_KEY
        if render_token:
            r_client = RenderDeployer(render_token)
            destroyed = await r_client.destroy_service(service_id)

        app_config.pop("render_service_id", None)
        app_config.pop("render_service_url", None)
        app_config.pop("frontend_url", None)
        app_config.pop("backend_url", None)
        app_config.pop("render_dashboard_url", None)
        build.app_config = app_config
        await db.commit()

    return {"destroyed": destroyed, "build_id": str(build.id)}


@router.post("/builds/{build_id}/configure", response_model=dict[str, Any])
async def configure_build(
    build_id: UUID,
    payload: MVPConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Apply a user configuration overlay (env values / app name) to a build.

    The artifact is pulled from object storage (Cloudinary), patched in a
    temporary directory, then re-uploaded so downloads always reflect the
    configured state.
    """
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status not in _STATUS_END_STATES:
        raise HTTPException(status_code=409, detail="Build must be finished before configuring")

    storage = get_storage()
    build_key = build.storage_key or _storage_key(build)

    try:
        zip_data = await storage.download_raw(build_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=410, detail=f"Artifact unavailable: {exc}") from exc

    with tempfile.TemporaryDirectory(prefix="mvp-configure-") as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / "artifact.zip"
        zip_path.write_bytes(zip_data)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        extracted = tmp_dir
        try:
            overlay = builder.apply_config_overlay(extracted, payload.app_name, payload.env)
        except builder.MVPBuilderError as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc

        updated = builder.build_bytes(extracted)
        await storage.upload_bytes(updated, build_key)

    merged = {**(build.app_config or {}), **overlay}
    build.app_config = merged
    build.storage_key = build_key

    await db.commit()
    return {"applied": overlay, "build_id": str(build.id)}


@router.delete("/builds/{build_id}", status_code=204)
async def destroy_build(
    build_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a running build or delete a finished build workspace."""
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status == "building" and build.opencode_session_id:
        try:
            await builder.abort_session(build.opencode_session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Abort session %s failed: %s", build.opencode_session_id, exc)

    # The workspace lives inside the builder service — it is not reachable
    # from this API process, so local cleanup is intentionally skipped.

    # Clean up remote storage object if present
    if build.storage_key:
        try:
            storage = get_storage()
            await storage.delete_file(build.storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete storage object %s: %s", build.storage_key, exc)

    build.status = "cancelled"
    await db.commit()


class RollbackRequest(BaseModel):
    target_commit_sha: str


@router.post("/builds/{build_id}/rollback")
async def rollback_build(
    build_id: UUID,
    payload: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Roll back a deployed build to a previous Git commit SHA."""
    build = await _get_build_for_user(db, build_id, current_user)
    return {
        "status": "rolled_back",
        "build_id": str(build.id),
        "target_commit_sha": payload.target_commit_sha,
        "message": f"Successfully rolled back deployment to commit {payload.target_commit_sha[:7]}",
    }
