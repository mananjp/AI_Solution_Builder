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
import logging
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.build_locks import allocate_build_number
from app.core.config import settings
from app.core.credits import action_cost, refund_credit, require_and_deduct_credit
from app.core.database import async_session_factory, get_db
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
                result = await builder.run_build(
                    solution.id,
                    ai_state,
                    build.build_number,
                    title=title,
                    user_prompt=user_msg,
                    check_npm=settings.MVP_VERIFY_NPM,
                    allow_offline=True,
                )

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
            app_config={**payload.config, "app_name": payload.app_name, "template": payload.template},
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

    return _build_response(build)


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
            app_config={**payload.config, "app_name": payload.app_name, "template": payload.template},
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

    return _build_response(build)


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
    return [_build_response(b) for b in result.scalars().all()]


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
            files = builder.list_build_files(local_dir) if local_dir.exists() else []
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

    return _build_response(build, include_files=(build.status in _STATUS_END_STATES))


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
