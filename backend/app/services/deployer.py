"""
AI Solution Builder — One-Click Deployer (Section 11)

Pushes a generated code manifest to a fresh GitHub repository using the
GitHub REST API and a Personal Access Token, then reports the repository
URL. Fail-open: raises DeployError with a human-readable message on any
GitHub/network failure.
"""

import json
import logging
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx

GH_API_BASE = "https://api.github.com"

logger = logging.getLogger(__name__)


class DeployError(RuntimeError):
    """Raised when a deployment cannot be completed."""


def _extract_mvp_files(root: Path) -> dict[str, str]:
    """Flatten a generated MVP workspace into the GitHub file map.

    Files under ``infra/`` are hoisted to the repo root when they are part of
    the standard Render/docker scaffold (``render.yaml``, ``docker-compose.yml``,
    ``README.md``, ``.github/*``) so Render's blueprint auto-detects them.
    """
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "__pycache__", ".next"} for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
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
    return files


async def deploy_build_workspace(
    *,
    gh_token: str,
    repo_name: str,
    archive_bytes: bytes,
    description: str = "",
    private: bool = False,
) -> dict[str, Any]:
    """Push a finished MVP build (as a ZIP archive) to a fresh GitHub repo.

    The archive is unpacked into a temporary directory — the API service must
    not rely on the builder service's local workspace. Returns the deployment
    result plus a ``file_count``.
    """
    with TemporaryDirectory(prefix="mvp-deploy-") as tmp:
        root = Path(tmp)
        artifact = root / "artifact.zip"
        artifact.write_bytes(archive_bytes)
        with zipfile.ZipFile(artifact, "r") as zf:
            zf.extractall(root)

        files = _extract_mvp_files(root)
        if not files:
            raise DeployError("Build archive contains no files to deploy")

        result = await deploy_to_github(
            gh_token,
            repo_name,
            files,
            description=description or "Auto-generated MVP by AI Solution Builder",
            private=private,
        )
        logger.info(
            "Deployed MVP %s -> %s (%d files, branch %s)",
            repo_name,
            result["url"],
            len(files),
            result["branch"],
        )
        return {**result, "file_count": len(files)}


def build_repo_files(bundle: dict[str, Any], workflow: str) -> dict[str, str]:
    """Produce the file tree pushed to GitHub for a solution bundle."""
    sql_schema = "-- Generated PostgreSQL Schema\n"
    api_spec: dict[str, Any] = {}
    for art in bundle.get("artifacts", []):
        if art["artifact_type"] == "database_schema" and art.get("content_text"):
            sql_schema = art["content_text"]
        if art["artifact_type"] == "api_spec" and art.get("content"):
            api_spec = art["content"]

    readme = (
        f"# {bundle.get('title', 'Solution')}\n"
        "Auto-generated from AI Solution Builder OS.\n\n"
        "## Quick Start\n```bash\n"
        "docker-compose up -d\n"
        "```\n\n### Endpoints\n"
        "`/api/v1` — Generated REST engine mounted on provisioned tables.\n"
    )

    return {
        "README.md": readme,
        "docker-compose.yml": (
            "services:\n"
            "  app:\n"
            "    build: .\n"
            "    ports: ['8000:8000']\n"
            "    environment:\n"
            "      - DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db\n"
            "    depends_on: [db]\n"
            "  db:\n"
            "    image: postgres:16-alpine\n"
            "    environment:\n"
            "      - POSTGRES_USER=postgres\n"
            "      - POSTGRES_PASSWORD=postgres\n"
            "      - POSTGRES_DB=app_db\n"
            "    volumes:\n"
            "      - ./init.sql:/docker-entrypoint-initdb.d/init.sql\n"
        ),
        "init.sql": sql_schema,
        "api_spec.json": json.dumps(api_spec, indent=2),
        ".github/workflows/deploy.yml": workflow,
    }


async def deploy_to_github(
    token: str,
    repo_name: str,
    files: dict[str, str],
    *,
    description: str = "",
    private: bool = False,
) -> dict[str, str]:
    """Create a GitHub repository, push the manifest, and return its URL."""
    if not token:
        raise DeployError("GITHUB_TOKEN is not configured on the server")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Create the repository.
        create_resp = await client.post(
            f"{GH_API_BASE}/user/repos",
            headers=headers,
            json={
                "name": repo_name,
                "description": description or "Auto-generated by AI Solution Builder",
                "private": private,
                "auto_init": False,
            },
        )
        if create_resp.status_code not in (200, 201):
            raise DeployError(
                f"Repo create failed ({create_resp.status_code}): {create_resp.text[:300]}"
            )

        owner = create_resp.json()["owner"]["login"]
        default_branch = create_resp.json().get("default_branch", "main")

        # 2. Push one file (README) to initialize the default branch ref.
        readme = files.get("README.md", "# Auto-generated solution\n")
        ref_url = f"{GH_API_BASE}/repos/{owner}/{repo_name}/contents/README.md"
        readme_resp = await client.put(
            ref_url,
            headers=headers,
            json={
                "message": "Initial deploy by AI Solution Builder",
                "content": _b64(readme.encode("utf-8")),
            },
        )
        if readme_resp.status_code not in (200, 201):
            raise DeployError(
                f"Initial commit failed ({readme_resp.status_code}): {readme_resp.text[:300]}"
            )

        # 3. Push the remaining files onto the default branch.
        remaining = {name: content for name, content in files.items() if name != "README.md"}
        for name, content in remaining.items():
            path = f"{GH_API_BASE}/repos/{owner}/{repo_name}/contents/{name}"
            response = await client.put(
                path,
                headers=headers,
                json={
                    "message": f"Add {name}",
                    "content": _b64(content.encode("utf-8")),
                    "branch": default_branch,
                },
            )
            if response.status_code not in (200, 201):
                raise DeployError(
                    f"Push of {name} failed ({response.status_code}): {response.text[:300]}"
                )

        repo_url = f"https://github.com/{owner}/{repo_name}"
        clone_url = f"https://github.com/{owner}/{repo_name}.git"
        logger.info("Deployed %s -> %s (%d files)", repo_name, repo_url, len(files))
        return {"url": repo_url, "clone_url": clone_url, "owner": owner, "branch": default_branch}


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")
