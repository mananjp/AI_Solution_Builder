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
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.credits import require_and_deduct_credit
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


async def _next_build_number(db: AsyncSession, solution_id: UUID) -> int:
    result = await db.execute(
        select(MVPBuild.build_number)
        .where(MVPBuild.solution_id == solution_id)
        .order_by(desc(MVPBuild.build_number))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    return (last or 0) + 1


def _build_response(build: MVPBuild, include_files: bool = False) -> MVPBuildResponse:
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

    return MVPBuildResponse(
        build_id=build.id,
        solution_id=build.solution_id,
        build_number=build.build_number,
        status=build.status,
        workspace_path=workspace_path,
        file_count=build.file_count,
        error_message=build.error_message,
        repo_url=build.repo_url,
        render_service_url=app_config.get("render_service_url"),
        render_dashboard_url=app_config.get("render_dashboard_url"),
        render_deploy_url=render_deploy_url,
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

            result = await builder.run_build(
                solution.id,
                ai_state,
                build.build_number,
                title=title,
                check_npm=settings.MVP_VERIFY_NPM,
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

            # Mark associated BuildJob completed
            job_res = await db.execute(select(BuildJob).where(BuildJob.build_id == build_id))
            job = job_res.scalar_one_or_none()
            if job:
                job.status = "completed"

            # Push the artifact to object storage (production: Cloudinary only,
            # enforced by ``get_storage()`` — no silent local fallback).
            key = _storage_key(build)
            storage = get_storage()
            zip_data = builder.build_bytes(result["local_dir"])
            await storage.upload_bytes(zip_data, key)
            del zip_data
            import gc
            gc.collect()

            build.storage_key = key
            logger.info(
                "MVP build %s complete — %d files, artifact uploaded to %s",
                build.id,
                result["file_count"],
                key,
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001 - persist any failure for retry
        logger.exception("MVP build %s failed", build_id)
        try:
            async with async_session_factory() as db:
                build = await db.get(MVPBuild, build_id)
                if build is not None:
                    build.status = "failed"
                    build.error_message = str(exc)[:1000]
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

    build_number = await _next_build_number(db, solution.id)
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
    if solution.status != "complete" and not payload.force and not payload.template:
        raise HTTPException(
            status_code=409,
            detail="Solution artifacts must be generated before building an MVP. Use force=true to override.",
        )

    await require_and_deduct_credit(
        db,
        current_user,
        "mvp_build",
        f"MVP build: {solution.title}",
        solution_id=solution.id,
    )

    build_number = await _next_build_number(db, solution.id)
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

    storage = get_storage()
    key = build.storage_key or _storage_key(build)

    url = await storage.get_download_url(key)
    if url:
        return RedirectResponse(url=url, status_code=307)

    try:
        data = await storage.download_raw(key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    filename = f"mvp_{build.solution_id.hex[:8]}_build{build.build_number}.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    if not gh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "No GitHub token configured on your profile. Save one via "
                "PATCH /api/v1/auth/me/settings, then retry."
            ),
        )

    storage = get_storage()
    build_key = build.storage_key or _storage_key(build)

    try:
        zip_data = await storage.download_raw(build_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=410, detail=str(exc)) from exc

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

    # Check if user has saved a Render API key
    raw_render_token = str((current_user.settings or {}).get("render_api_key", ""))
    render_token = decrypt_secret(raw_render_token) if raw_render_token else ""

    render_deploy_url = get_1click_deploy_url(result["url"])
    render_service_id = None
    render_service_url = None
    render_dashboard_url = None
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
            render_service_url = r_res.get("service_url")
            render_dashboard_url = r_res.get("dashboard_url")
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
        "render_dashboard_url": render_dashboard_url,
        "render_deploy_url": render_deploy_url,
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
        "render_dashboard_url": render_dashboard_url,
        "render_deploy_url": render_deploy_url,
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
        if render_token:
            r_client = RenderDeployer(render_token)
            destroyed = await r_client.destroy_service(service_id)

        app_config.pop("render_service_id", None)
        app_config.pop("render_service_url", None)
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
