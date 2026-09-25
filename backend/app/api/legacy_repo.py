"""
AI Solution Builder — Legacy Repository API Routes

Handles legacy codebase inspection, stack & architecture analysis, credential verification,
controlled parallel modernization, and feature extensions (AI Chatbot).
"""

import io
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.legacy_repo import (
    CredentialValidateRequest,
    CredentialValidateResponse,
    LegacyRepoAnalyzeRequest,
    ModernizeRequest,
    ModernizeResponse,
)
from app.services.legacy_repo.analyzer import LegacyRepoAnalyzer
from app.services.legacy_repo.boundary import ScopeBoundaryViolation, assert_safe_boundary
from app.services.legacy_repo.credentials import CredentialValidator, mask_secret
from app.services.legacy_repo.modernizer import LegacyRepoModernizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legacy-repo", tags=["Legacy Repository Modernizer"])


def _extract_zip_to_workspace(zip_bytes: bytes, workspace_dir: Path) -> Path:
    """Extract zip archive safely without path traversal."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.infolist():
            # Prevent zip slip
            extracted_path = (workspace_dir / member.filename).resolve()
            if not str(extracted_path).startswith(str(workspace_dir.resolve())):
                raise HTTPException(status_code=400, detail="Invalid zip archive: path traversal detected")
        zf.extractall(workspace_dir)
    return workspace_dir


@router.post("/analyze")
async def analyze_legacy_repository(
    payload: LegacyRepoAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Inspect and analyze an existing legacy repository via local path or GitHub URL."""
    target_dir: Optional[Path] = None
    cleanup_temp = False

    try:
        if payload.local_path:
            target_dir = Path(payload.local_path)

        elif payload.github_repo_url:
            repo_url = payload.github_repo_url.rstrip("/")
            parts = repo_url.split("/")
            if len(parts) < 2:
                raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
            owner, repo = parts[-2], parts[-1]
            zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(zip_url)
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Could not fetch repository archive from GitHub: {resp.text[:120]}",
                    )
                temp_id = uuid4().hex[:10]
                staging_dir = Path(tempfile.gettempdir()) / f"legacy_gh_{owner}_{repo}_{temp_id}"
                target_dir = _extract_zip_to_workspace(resp.content, staging_dir)
                cleanup_temp = True
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either local_path or github_repo_url",
            )

        # Strictly assert safe boundary (fails immediately if sutra_os is touched)
        assert_safe_boundary(target_dir, action="analyze")

        analyzer = LegacyRepoAnalyzer(target_dir)
        report = analyzer.analyze()
        return report

    except ScopeBoundaryViolation as sbv:
        logger.error("Scope boundary violation in legacy analyzer: %s", sbv)
        raise HTTPException(status_code=403, detail=str(sbv))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Legacy repository analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if cleanup_temp and target_dir and target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)


@router.post("/analyze-upload")
async def analyze_uploaded_repository_zip(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Inspect and analyze an uploaded repository ZIP archive."""
    staging_dir: Optional[Path] = None
    try:
        max_bytes = 50 * 1024 * 1024
        contents = await file.read(max_bytes + 1)
        if len(contents) > max_bytes:
            raise HTTPException(status_code=413, detail="Repository ZIP too large (max 50MB)")

        temp_id = uuid4().hex[:10]
        staging_dir = Path(tempfile.gettempdir()) / f"legacy_upload_{temp_id}"
        target_dir = _extract_zip_to_workspace(contents, staging_dir)

        assert_safe_boundary(target_dir, action="analyze")
        analyzer = LegacyRepoAnalyzer(target_dir)
        report = analyzer.analyze()
        return report

    except ScopeBoundaryViolation as sbv:
        logger.error("Scope boundary violation in legacy upload analyzer: %s", sbv)
        raise HTTPException(status_code=403, detail=str(sbv))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Legacy upload analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if staging_dir and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


@router.post("/validate-credentials", response_model=CredentialValidateResponse)
async def validate_credential(
    payload: CredentialValidateRequest,
    current_user: User = Depends(get_current_user),
) -> CredentialValidateResponse:
    """Validate format and perform minimal connection test for an API credential."""
    format_ok, msg = CredentialValidator.validate_format(payload.key_name, payload.key_value)
    if not format_ok:
        return CredentialValidateResponse(
            key_name=payload.key_name,
            format_valid=False,
            connection_tested=False,
            connection_success=False,
            message=msg,
            masked_key=mask_secret(payload.key_value),
        )

    # Test connectivity
    conn_ok, conn_msg = await CredentialValidator.test_connectivity(payload.key_name, payload.key_value)
    return CredentialValidateResponse(
        key_name=payload.key_name,
        format_valid=True,
        connection_tested=True,
        connection_success=conn_ok,
        message=conn_msg,
        masked_key=mask_secret(payload.key_value),
    )


@router.post("/modernize", response_model=ModernizeResponse)
async def modernize_legacy_repository(
    payload: ModernizeRequest,
    current_user: User = Depends(get_current_user),
) -> ModernizeResponse:
    """Execute safe modernization and requested feature extensions (AI Chatbot)."""
    if not payload.local_path and not payload.github_repo_url:
        raise HTTPException(status_code=400, detail="Must provide either local_path or github_repo_url")

    target_dir: Optional[Path] = None
    if payload.local_path:
        target_dir = Path(payload.local_path)
    else:
        # Fetch GitHub repository
        repo_url = (payload.github_repo_url or "").rstrip("/")
        parts = repo_url.split("/")
        owner, repo = parts[-2], parts[-1]
        zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(zip_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Could not fetch GitHub repository archive")
            temp_id = uuid4().hex[:10]
            staging_dir = Path(tempfile.gettempdir()) / f"legacy_mod_{owner}_{repo}_{temp_id}"
            target_dir = _extract_zip_to_workspace(resp.content, staging_dir)

    try:
        # Strict boundary validation
        assert_safe_boundary(target_dir, action="modernize")

        modernizer = LegacyRepoModernizer(target_dir, create_isolated_copy=True)
        result = await modernizer.modernize(
            requested_features=payload.requested_features,
            credentials=payload.credentials,
        )
        return ModernizeResponse(**result)

    except ScopeBoundaryViolation as sbv:
        logger.error("Scope boundary violation in legacy modernizer: %s", sbv)
        raise HTTPException(status_code=403, detail=str(sbv))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Modernization execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/download/{build_id}")
async def download_modernized_build(
    build_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download the packaged modernized repository ZIP artifact."""
    zip_path = Path(settings.MVP_BUILD_DIR).resolve() / "legacy_builds" / f"{build_id}_modernized.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Modernized build artifact not found")

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"modernized_repo_{build_id}.zip",
    )
