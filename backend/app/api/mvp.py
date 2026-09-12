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
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credits import require_and_deduct_credit
from app.core.database import async_session_factory, get_db
from app.core.secrets import decrypt_secret
from app.core.security import get_current_user
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
    MVPTemplateResponse,
)
from app.services import mvp_builder as builder
from app.services import templates
from app.services.deployer import DeployError, deploy_to_github
from app.services.storage import LocalStorage, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mvp", tags=["OpenCode MVP Builder"])

_STATUS_END_STATES = {"complete", "failed", "cancelled"}

_build_tasks: set[asyncio.Task[None]] = set()


def _spawn_build_job(build_id: UUID) -> None:
    """Run a build in a background task, holding a strong reference so the
    event loop never garbage-collects a pending task mid-build."""
    task = asyncio.create_task(_run_build_job(build_id), name=f"mvp-build-{build_id}")
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
        workspace = Path(build.workspace_path)
        if workspace.exists():
            files = [
                MVPFileEntry(path=p, size=0, is_dir=False)
                for p in builder.relative_paths(workspace)
            ]
    # Only expose a project-relative workspace slug (solution/build), never the
    # server filesystem path.
    workspace_path = str(Path(build.workspace_path).relative_to(Path(build.workspace_path).parent.parent)) \
        if build.workspace_path else ""
    return MVPBuildResponse(
        build_id=build.id,
        solution_id=build.solution_id,
        build_number=build.build_number,
        status=build.status,
        workspace_path=workspace_path,
        file_count=build.file_count,
        error_message=build.error_message,
        repo_url=build.repo_url,
        files=files,
    )


async def _deploy_workspace_to_github(
    *,
    gh_token: str,
    repo_name: str,
    workspace_path: str,
    description: str,
    private: bool,
) -> dict[str, Any]:
    """Flatten a build workspace into a file map and push it to GitHub."""
    root = Path(workspace_path)
    if not root.is_dir():
        raise DeployError("Build workspace is missing on the server")

    files: dict[str, str] = {}
    for rel in builder.relative_paths(root):
        path = root / rel
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if rel.startswith("infra/"):
            top = rel[len("infra/") :]
            if (
                top == "render.yaml"
                or top == "docker-compose.yml"
                or top == "README.md"
                or top.startswith(".github/")
            ):
                files[top] = content
            else:
                files[rel] = content
        else:
            files[rel] = content

    if not files:
        raise DeployError("Build workspace contains no files to deploy")

    description = description or "Auto-generated MVP by AI Solution Builder"
    result = await deploy_to_github(
        gh_token, repo_name, files, description=description, private=private
    )
    logger.info(
        "Deployed MVP %s -> %s (%d files, branch %s)",
        repo_name,
        result["url"],
        len(files),
        result["branch"],
    )
    return {**result, "file_count": len(files)}


async def _run_build_job(build_id: UUID) -> None:
    """Background task: drive the OpenCode sidecar to complete a build."""
    try:
        async with async_session_factory() as db:
            build = await db.get(MVPBuild, build_id)
            if build is None:
                return
            solution = await db.get(Solution, build.solution_id)
            if solution is None:
                build.status = "failed"
                build.error_message = "Solution not found"
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

            result = await builder.run_build(solution.id, ai_state, build.build_number, title=title)

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
            build.error_message = None

            # Upload to Cloudinary if configured
            storage = get_storage()
            if not isinstance(storage, LocalStorage):
                key = f"builds/{build.solution_id}/build_{build.build_number}.zip"
                zip_file = builder.zip_path_for_build(result["local_dir"])
                try:
                    await storage.upload_file(zip_file, key)
                    build.storage_key = key
                    logger.info("Cloudinary upload succeeded for build %s (key=%s)", build.id, key)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Cloudinary upload failed for build %s, falling back to local: %s",
                        build.id,
                        exc,
                    )
                finally:
                    zip_file.unlink(missing_ok=True)

            logger.info(
                "MVP build %s complete — %d files in %s",
                build.id,
                result["file_count"],
                result["local_dir"],
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
                    await db.commit()
        except Exception as persist_exc:  # noqa: BLE001
            logger.error("Failed to persist MVP build failure: %s", persist_exc)


@router.get("/templates", response_model=list[MVPTemplateResponse])
async def list_templates(
    current_user: User = Depends(get_current_user),
) -> list[MVPTemplateResponse]:
    """List the small, deployable starter templates users can build from."""
    return [MVPTemplateResponse(**t) for t in templates.list_templates()]


@router.post("/{solution_id}/build", response_model=MVPBuildResponse)
async def trigger_build(
    solution_id: UUID,
    payload: MVPBuildRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MVPBuildResponse:
    """Kick off an OpenCode MVP build for a completed solution (async)."""
    solution = await _get_solution_for_user(db, solution_id, current_user)
    if solution.status != "complete" and not payload.force:
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
        status="building",
        workspace_path=str(workspace),
        app_config={**payload.config, "app_name": payload.app_name, "template": payload.template},
    )
    db.add(build)
    await db.commit()
    await db.refresh(build)

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
    """Get build status, error details, and the generated file tree."""
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status == "building":
        # Best-effort: reflect a locally-visible file count while running.
        workspace = Path(build.workspace_path)
        if workspace.exists():
            build.file_count = len(builder.list_build_files(workspace))
    return _build_response(build, include_files=(build.status in _STATUS_END_STATES))


@router.get("/builds/{build_id}/download")
async def download_build(
    build_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the generated MVP project as a ZIP archive.

    When a build has been uploaded to remote storage (``storage_key`` is set),
    the endpoint returns a 307 redirect to Cloudinary's secure URL.
    Otherwise it falls through to the original local-disk StreamingResponse.
    """
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status != "complete":
        raise HTTPException(
            status_code=409, detail=f"Build is not complete (status={build.status})"
        )

    # Prefer remote storage URL if available
    if build.storage_key:
        storage = get_storage()
        url = await storage.get_download_url(build.storage_key)
        if url:
            return RedirectResponse(url=url, status_code=307)

    # Fallthrough: existing local-disk StreamingResponse
    try:
        buffer = builder.package_build(build.workspace_path)
    except builder.MVPBuilderError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    filename = f"mvp_{build.solution_id.hex[:8]}_build{build.build_number}.zip"
    return StreamingResponse(
        buffer,
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

    try:
        result = await _deploy_workspace_to_github(
            gh_token=gh_token,
            repo_name=payload.repo_name,
            workspace_path=build.workspace_path,
            description=payload.description,
            private=payload.private,
        )
    except DeployError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    build.repo_url = result["url"]
    build.app_config = {**(build.app_config or {}), "repo_url": result["url"]}
    await db.commit()
    return {
        "repo_url": result["url"],
        "clone_url": result["clone_url"],
        "branch": result["branch"],
        "file_count": result["file_count"],
        "render_blueprint": "connected on Render via render.yaml in repo root",
    }


@router.post("/builds/{build_id}/configure", response_model=dict[str, Any])
async def configure_build(
    build_id: UUID,
    payload: MVPConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Apply a user configuration overlay (env values / app name) to a build."""
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status not in _STATUS_END_STATES:
        raise HTTPException(status_code=409, detail="Build must be finished before configuring")

    try:
        overlay = builder.apply_config_overlay(build.workspace_path, payload.app_name, payload.env)
    except builder.MVPBuilderError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    merged = {**(build.app_config or {}), **overlay}
    build.app_config = merged

    # Invalidate stale remote artifact — the workspace on disk has changed,
    # so the previously-uploaded ZIP no longer reflects the configured state.
    if build.storage_key:
        try:
            storage = get_storage()
            await storage.delete_file(build.storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to delete stale storage object %s after configure: %s",
                build.storage_key,
                exc,
            )
        build.storage_key = None

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

    builder.cleanup_build(build.workspace_path)

    # Clean up remote storage object if present
    if build.storage_key:
        try:
            storage = get_storage()
            await storage.delete_file(build.storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete storage object %s: %s", build.storage_key, exc)

    build.status = "cancelled"
    await db.commit()
