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
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mvp", tags=["OpenCode MVP Builder"])

_STATUS_END_STATES = {"complete", "failed", "cancelled"}


def _module_from_concept(concept: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", concept.lower())
    stop_words = {"a", "an", "the", "of", "for", "to", "and", "with", "app", "application"}
    useful = [word for word in words if word not in stop_words][:4]
    return "_".join(useful) or "custom_mvp"


def _product_type_from_concept(concept: str) -> str:
    text = concept.lower()
    if any(term in text for term in ("landing page", "marketing page", "homepage", "pricing")):
        return "landing_page"
    if any(term in text for term in ("dashboard", "admin", "analytics", "crm", "portal")):
        return "dashboard_app"
    if any(term in text for term in ("marketplace", "store", "ecommerce", "e-commerce", "shop")):
        return "commerce_app"
    if any(term in text for term in ("booking", "calendar", "appointment", "reservation")):
        return "booking_app"
    return "full_stack_app"


def _seed_ai_state_from_concept(
    *, concept: str, title: str, existing_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    state = dict(existing_state or {})
    module = _module_from_concept(concept)
    state.setdefault("solution_title", title or concept[:80] or "Custom MVP")
    state.setdefault("business_description", concept)
    state.setdefault("industry", "general")
    state.setdefault("product_type", _product_type_from_concept(concept))
    state.setdefault("confirmed_modules", [module])
    state.setdefault("identified_solutions", [module])
    return state


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


async def _active_build_for_solution(db: AsyncSession, solution_id: UUID) -> MVPBuild | None:
    result = await db.execute(
        select(MVPBuild)
        .where(
            MVPBuild.solution_id == solution_id,
            MVPBuild.status.in_(["pending", "building"]),
        )
        .order_by(desc(MVPBuild.build_number))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _build_response(build: MVPBuild, include_files: bool = False) -> MVPBuildResponse:
    files: list[MVPFileEntry] = []
    if include_files:
        workspace = Path(build.workspace_path)
        if workspace.exists():
            files = [
                MVPFileEntry(path=p, size=0, is_dir=False)
                for p in builder.relative_paths(workspace)
            ]
    return MVPBuildResponse(
        build_id=build.id,
        solution_id=build.solution_id,
        build_number=build.build_number,
        status=build.status,
        workspace_path=build.workspace_path,
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

            config = build.app_config or {}
            build_concept = str(config.get("build_concept") or "").strip()
            title = config.get("app_name") or solution.title or build_concept or "Custom MVP"

            ai_state = solution.ai_state or {}
            template_slug = config.get("template")
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
            elif build_concept and not (
                ai_state.get("confirmed_modules") or ai_state.get("identified_solutions")
            ):
                ai_state = _seed_ai_state_from_concept(
                    concept=build_concept,
                    title=title,
                    existing_state=ai_state,
                )

            if build_concept:
                ai_state = {
                    **ai_state,
                    "business_description": build_concept,
                    "product_type": ai_state.get("product_type")
                    or _product_type_from_concept(build_concept),
                }

            result = await builder.run_build(solution.id, ai_state, build.build_number, title=title)
            build.status = "complete"
            build.opencode_session_id = result["session_id"]
            build.file_count = result["file_count"]
            build.error_message = None
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
    if solution.status not in ("complete", "generating") and not payload.force:
        raise HTTPException(
            status_code=409,
            detail="Solution artifacts must be generated before building an MVP. Generate blueprints first, then build.",
        )

    existing = await _active_build_for_solution(db, solution.id)
    if existing is not None:
        logger.info(
            "Reusing active MVP build for solution=%s (build=%s, status=%s)",
            solution.id,
            existing.build_number,
            existing.status,
        )
        return _build_response(existing)

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

    task = asyncio.create_task(_run_build_job(build.id))
    task.add_done_callback(
        lambda _t: None  # failures logged in the job itself
    )

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
    builds = []
    for b in result.scalars().all():
        if b.status == "building":
            workspace = Path(b.workspace_path)
            if workspace.exists():
                b.file_count = len(builder.list_build_files(workspace))
        builds.append(_build_response(b, include_files=True))
    return builds


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
    return _build_response(build, include_files=True)


@router.get("/builds/{build_id}/download")
async def download_build(
    build_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download the generated MVP project as a ZIP archive."""
    build = await _get_build_for_user(db, build_id, current_user)
    if build.status != "complete":
        raise HTTPException(
            status_code=409, detail=f"Build is not complete (status={build.status})"
        )
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

    gh_token = str((current_user.settings or {}).get("github_token", ""))
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
    build.status = "cancelled"
    await db.commit()
