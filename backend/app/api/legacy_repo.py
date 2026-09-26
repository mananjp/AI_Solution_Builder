"""
AI Solution Builder — Legacy Repository API Routes

Handles legacy codebase inspection, stack & architecture analysis, credential verification,
controlled parallel modernization, and feature extensions (AI Chatbot).
"""

import io
import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.core.secrets import decrypt_secret
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


def _resolve_github_token(payload_token: Optional[str], current_user: Optional[User]) -> Optional[str]:
    """Resolve GitHub token from request payload, user profile settings (decrypted), or app environment."""
    if payload_token and payload_token.strip():
        return payload_token.strip()

    if current_user and current_user.settings:
        raw_token = str(current_user.settings.get("github_token", ""))
        if raw_token:
            decrypted = decrypt_secret(raw_token)
            if decrypted and decrypted.strip():
                return decrypted.strip()

    if getattr(settings, "GITHUB_TOKEN", None):
        return settings.GITHUB_TOKEN.strip()

    return None


def _parse_github_owner_repo(url: str) -> tuple[str, str]:
    """Extract owner and repository name from GitHub URL safely."""
    raw = url.strip()
    if raw.startswith("git@github.com:"):
        path = raw[len("git@github.com:") :]
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1].removesuffix(".git")

    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL. Expected format: https://github.com/owner/repository",
        )
    owner = path_parts[0]
    repo = path_parts[1].removesuffix(".git")
    return owner, repo


async def _fetch_github_zipball(owner: str, repo: str, token: Optional[str] = None) -> bytes:
    """Download repository zipball from GitHub with authentication and redirect preservation."""
    zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Solution-Builder",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
        try:
            resp = await client.get(zip_url, headers=headers)
        except Exception as exc:
            logger.error("GitHub API request failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"Failed to connect to GitHub API: {str(exc)}")

        # Handle 302 Found redirecting to codeload.github.com
        if resp.status_code in (301, 302, 307, 308):
            redirect_url = resp.headers.get("Location")
            if not redirect_url:
                raise HTTPException(status_code=502, detail="GitHub redirect missing Location header")

            # Forward authorization header if domain is github.com / codeload.github.com
            redirect_headers = {"User-Agent": "AI-Solution-Builder"}
            if token and ("github.com" in redirect_url or "githubusercontent.com" in redirect_url):
                redirect_headers["Authorization"] = f"Bearer {token}"

            try:
                redirect_resp = await client.get(redirect_url, headers=redirect_headers, follow_redirects=True)
            except Exception as exc:
                logger.error("GitHub codeload redirect download failed: %s", exc)
                raise HTTPException(
                    status_code=502, detail=f"Failed to download repository archive from GitHub: {str(exc)}"
                )

            if redirect_resp.status_code != 200:
                raise HTTPException(
                    status_code=redirect_resp.status_code,
                    detail=f"Could not download repository archive from GitHub ({redirect_resp.status_code}): {redirect_resp.text[:150]}",
                )
            return redirect_resp.content

        elif resp.status_code == 200:
            return resp.content
        else:
            detail_msg = resp.text[:180]
            if resp.status_code == 403 and "rate limit" in detail_msg.lower():
                detail_msg = (
                    "GitHub API rate limit exceeded. Please ensure your GitHub Personal Access Token "
                    "is saved in Settings or provided in the token field."
                )
            elif resp.status_code == 404:
                detail_msg = (
                    f"Repository '{owner}/{repo}' not found on GitHub. If this is a private repository, "
                    "please ensure your GitHub Personal Access Token has 'repo' permissions."
                )
            elif resp.status_code == 401:
                detail_msg = "Invalid or expired GitHub Personal Access Token. Please verify your token in Settings."

            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Could not fetch repository archive from GitHub: {detail_msg}",
            )


def _ensure_demo_sample_repo() -> Path:
    """Generate or retrieve a realistic mock legacy CRM repository fixture for demo exploration."""
    demo_dir = Path(tempfile.gettempdir()) / "ai_builder_demo_legacy_crm"
    demo_dir.mkdir(parents=True, exist_ok=True)

    pkg_file = demo_dir / "package.json"
    if not pkg_file.exists():
        pkg_data = {
            "name": "legacy-crm-app",
            "version": "1.0.0",
            "description": "Legacy Customer Relationship Management Dashboard",
            "scripts": {
                "start": "node server/index.js",
                "build": "webpack --mode production",
                "test": "jest",
            },
            "dependencies": {
                "react": "16.8.0",
                "react-dom": "16.8.0",
                "express": "4.16.0",
                "request": "^2.88.2",
                "moment": "^2.29.1",
                "body-parser": "^1.18.3",
                "cors": "^2.8.5",
            },
            "devDependencies": {
                "webpack": "^4.44.0",
                "webpack-cli": "^3.3.12",
                "babel-loader": "^8.0.6",
                "@babel/core": "^7.9.0",
            },
        }
        pkg_file.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

        server_dir = demo_dir / "server"
        server_dir.mkdir(exist_ok=True)
        (server_dir / "index.js").write_text(
            "const express = require('express');\nconst cors = require('cors');\nconst app = express();\n"
            "app.use(cors());\napp.use(express.json());\n\n"
            "// Legacy CRM Customer APIs\n"
            "app.get('/api/customers', (req, res) => {\n"
            "    res.json([\n"
            "        { id: 1, name: 'Acme Corp', tier: 'enterprise', status: 'active' },\n"
            "        { id: 2, name: 'Globex Inc', tier: 'growth', status: 'pending' },\n"
            "    ]);\n"
            "});\n\n"
            "app.listen(3001, () => console.log('Legacy CRM server running on port 3001'));\n",
            encoding="utf-8",
        )

        client_dir = demo_dir / "src"
        client_dir.mkdir(exist_ok=True)
        (client_dir / "App.js").write_text(
            "import React, { Component } from 'react';\nimport moment from 'moment';\n\n"
            "class App extends Component {\n"
            "    render() {\n"
            "        return (\n"
            "            <div className=\"crm-container\">\n"
            "                <h1>Legacy CRM Portal</h1>\n"
            "                <p>System Date: {moment().format('LL')}</p>\n"
            "            </div>\n"
            "        );\n"
            "    }\n"
            "}\nexport default App;\n",
            encoding="utf-8",
        )

        assets_dir = demo_dir / "public" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="#f59e0b"/></svg>',
            encoding="utf-8",
        )

    return demo_dir


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

    # Unwrap single root folder if created by GitHub zipball
    subdirs = [p for p in workspace_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
    files = [p for p in workspace_dir.iterdir() if p.is_file()]
    if len(subdirs) == 1 and len(files) == 0:
        return subdirs[0]

    return workspace_dir


@router.post("/analyze")
async def analyze_legacy_repository(
    payload: LegacyRepoAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Inspect and analyze an existing legacy repository via local path or GitHub URL."""
    target_dir: Optional[Path] = None
    staging_dir: Optional[Path] = None
    cleanup_temp = False

    try:
        if payload.local_path:
            raw_path = payload.local_path.strip()
            if raw_path in ("sample_legacy_repo", "sample_legacy_crm", "demo", ""):
                target_dir = _ensure_demo_sample_repo()
            else:
                target_dir = Path(raw_path)
                if not target_dir.exists():
                    cand = Path(__file__).resolve().parents[2] / raw_path
                    if cand.exists():
                        target_dir = cand
                    elif "sample" in raw_path.lower():
                        target_dir = _ensure_demo_sample_repo()
                    else:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Target repository path does not exist on server: {raw_path}",
                        )

        elif payload.github_repo_url:
            owner, repo = _parse_github_owner_repo(payload.github_repo_url)
            token = _resolve_github_token(payload.github_token, current_user)
            zip_content = await _fetch_github_zipball(owner, repo, token)

            temp_id = uuid4().hex[:10]
            staging_dir = Path(tempfile.gettempdir()) / f"legacy_gh_{owner}_{repo}_{temp_id}"
            target_dir = _extract_zip_to_workspace(zip_content, staging_dir)
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
        # Preserve staging_dir so the subsequent modernize call can reuse the extracted files without re-fetching
        pass


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
        # Preserve staging_dir so the subsequent modernize call can operate on the uploaded codebase
        pass


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
    staging_dir: Optional[Path] = None
    cleanup_temp = False

    try:
        # 1. Check local path if provided and exists
        if payload.local_path:
            raw_path = payload.local_path.strip()
            if raw_path in ("sample_legacy_repo", "sample_legacy_crm", "demo", ""):
                target_dir = _ensure_demo_sample_repo()
            else:
                cand = Path(raw_path)
                if cand.exists():
                    target_dir = cand
                else:
                    cand_workspace = Path(__file__).resolve().parents[2] / raw_path
                    if cand_workspace.exists():
                        target_dir = cand_workspace
                    elif "sample" in raw_path.lower():
                        target_dir = _ensure_demo_sample_repo()

        # 2. If target directory does not exist or wasn't provided, but github_repo_url is given, fetch from GitHub
        if (not target_dir or not target_dir.exists()) and payload.github_repo_url:
            owner, repo = _parse_github_owner_repo(payload.github_repo_url)
            token = _resolve_github_token(payload.github_token, current_user)
            zip_content = await _fetch_github_zipball(owner, repo, token)

            temp_id = uuid4().hex[:10]
            staging_dir = Path(tempfile.gettempdir()) / f"legacy_mod_{owner}_{repo}_{temp_id}"
            target_dir = _extract_zip_to_workspace(zip_content, staging_dir)
            cleanup_temp = True

        # 3. If target_dir is still missing, raise descriptive 404
        if not target_dir or not target_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Target repository path does not exist on server: {payload.local_path or payload.github_repo_url}",
            )

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
    finally:
        if cleanup_temp:
            dir_to_remove = staging_dir if staging_dir and staging_dir.exists() else target_dir
            if dir_to_remove and dir_to_remove.exists():
                shutil.rmtree(dir_to_remove, ignore_errors=True)


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
