"""
AI Solution Builder — One-Click Deployer (Section 11)

Pushes a generated code manifest to a fresh GitHub repository using the
GitHub REST API and a Personal Access Token, then reports the repository
URL. Fail-open: raises DeployError with a human-readable message on any
GitHub/network failure.
"""

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx

from app.services.security.archive import safe_extract_zip

GH_API_BASE = "https://api.github.com"

logger = logging.getLogger(__name__)


class DeployError(RuntimeError):
    """Raised when a deployment cannot be completed."""


def _sanitize_render_yaml(content: str) -> str:
    """Ensure render.yaml conforms to Render Blueprint specification."""
    if not content:
        return content

    import re

    # 1. If legacy format has 'type: pgsql' under services, migrate to root databases block
    if "type: pgsql" in content and "databases:" not in content:
        db_match = re.search(r"name:\s*([^\s]+-db)", content)
        db_name = db_match.group(1) if db_match else "app-db"
        clean_db = re.sub(r"[^a-zA-Z0-9_]", "_", db_name.replace("-db", "")).lower() or "app"

        # Remove only the pgsql service block
        content = re.sub(
            r"\n\s*-\s*name:\s*[^\n]+-db\s*\n(?:\s*(?:type|plan|database|ipAllowList):[^\n]*\n?)*",
            "",
            content,
        )
        db_block = (
            f"databases:\n"
            f"  - name: {db_name}\n"
            f"    databaseName: {clean_db}\n"
            f"    user: {clean_db}\n"
            f"    plan: free\n"
            f"    ipAllowList: []\n\n"
        )
        content = db_block + content.lstrip()

    # 2. Ensure dockerContext is present for backend and frontend
    if (
        "dockerfilePath: ./backend/Dockerfile" in content
        and "dockerContext: ./backend" not in content
    ):
        content = content.replace(
            "dockerfilePath: ./backend/Dockerfile",
            "dockerContext: ./backend\n    dockerfilePath: ./backend/Dockerfile",
        )
    if (
        "dockerfilePath: ./frontend/Dockerfile" in content
        and "dockerContext: ./frontend" not in content
    ):
        content = content.replace(
            "dockerfilePath: ./frontend/Dockerfile",
            "dockerContext: ./frontend\n    dockerfilePath: ./frontend/Dockerfile",
        )

    # 3. Strip conflicting build/start commands for docker runtime
    content = re.sub(r"\s+buildCommand:\s*npm[^\n]+", "", content)
    content = re.sub(r"\s+startCommand:\s*npm[^\n]+", "", content)

    # 4. Use plan: free for services so users aren't blocked on free tier
    content = content.replace("plan: starter", "plan: free")

    return content


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

    if "render.yaml" in files:
        files["render.yaml"] = _sanitize_render_yaml(files["render.yaml"])
        files["infra/render.yaml"] = files["render.yaml"]
    elif "infra/render.yaml" in files:
        files["render.yaml"] = _sanitize_render_yaml(files["infra/render.yaml"])
        files["infra/render.yaml"] = files["render.yaml"]

    # Guarantee frontend/src/lib/api.ts and public/.gitkeep are in deployed repo
    if any(k.startswith("frontend/src/") for k in files) and "frontend/src/lib/api.ts" not in files:
        from app.services.templates import _API_CLIENT_TS

        files["frontend/src/lib/api.ts"] = _API_CLIENT_TS
    if any(k.startswith("frontend/") for k in files) and "frontend/public/.gitkeep" not in files:
        files["frontend/public/.gitkeep"] = ""

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
        safe_extract_zip(archive_bytes, root)

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

    async with httpx.AsyncClient(timeout=45.0) as client:
        # 1. Create the repository or discover existing one.
        # auto_init=True ensures the default branch and initial commit exist immediately.
        create_resp = await client.post(
            f"{GH_API_BASE}/user/repos",
            headers=headers,
            json={
                "name": repo_name,
                "description": description or "Auto-generated by AI Solution Builder",
                "private": private,
                "auto_init": True,
            },
        )

        owner = None
        default_branch = "main"

        if create_resp.status_code in (200, 201):
            owner = create_resp.json().get("owner", {}).get("login")
            default_branch = create_resp.json().get("default_branch", "main")
        elif create_resp.status_code == 422 and "already exists" in create_resp.text:
            # Repository already exists on this account — reuse and update it cleanly!
            user_resp = await client.get(f"{GH_API_BASE}/user", headers=headers)
            if user_resp.status_code == 200:
                owner = user_resp.json().get("login")
            if not owner:
                owner = repo_name.split("/")[0] if "/" in repo_name else "user"
            repo_get = await client.get(f"{GH_API_BASE}/repos/{owner}/{repo_name}", headers=headers)
            if repo_get.status_code in (200, 201):
                default_branch = repo_get.json().get("default_branch", "main")
                with contextlib.suppress(Exception):
                    await client.patch(
                        f"{GH_API_BASE}/repos/{owner}/{repo_name}",
                        headers=headers,
                        json={"private": private},
                    )
            logger.info("Target repo %s/%s already exists; updating in-place", owner, repo_name)
        else:
            raise DeployError(
                f"Repo create failed ({create_resp.status_code}): {create_resp.text[:300]}"
            )

        if not owner:
            owner = "user"

        # 2. Query branch ref to check if default branch commit exists
        parent_commit_sha: str | None = None
        base_tree_sha: str | None = None
        ref_url = f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/ref/heads/{default_branch}"
        ref_resp = await client.get(ref_url, headers=headers)
        if ref_resp.status_code == 200:
            parent_commit_sha = ref_resp.json().get("object", {}).get("sha")
            if parent_commit_sha:
                commit_resp = await client.get(
                    f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/commits/{parent_commit_sha}",
                    headers=headers,
                )
                if commit_resp.status_code == 200:
                    base_tree_sha = commit_resp.json().get("tree", {}).get("sha")

        # If the repository has no commits yet (e.g., created empty), initialize with README.md
        if not parent_commit_sha:
            readme = files.get("README.md", "# Auto-generated solution\n")
            init_url = f"{GH_API_BASE}/repos/{owner}/{repo_name}/contents/README.md"
            init_resp = await client.put(
                init_url,
                headers=headers,
                json={
                    "message": "Initial deploy by AI Solution Builder",
                    "content": _b64(readme.encode("utf-8")),
                },
            )
            if init_resp.status_code in (200, 201):
                ref_resp = await client.get(ref_url, headers=headers)
                if ref_resp.status_code == 200:
                    parent_commit_sha = ref_resp.json().get("object", {}).get("sha")

        # 3. Attempt Atomic Git Data API deployment (Blobs -> Tree -> Commit -> Ref)
        # This completely eliminates file-by-file 409 SHA conflicts and race conditions.
        atomic_success = False
        patch_fn = getattr(client, "patch", None)

        if patch_fn and parent_commit_sha:
            try:
                semaphore = asyncio.Semaphore(8)
                blob_shas: dict[str, str] = {}

                async def _create_blob(name: str, content: str) -> None:
                    async with semaphore:
                        b_resp = await client.post(
                            f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/blobs",
                            headers=headers,
                            json={"content": _b64(content.encode("utf-8")), "encoding": "base64"},
                        )
                        if b_resp.status_code in (200, 201):
                            sha = b_resp.json().get("sha")
                            if sha:
                                blob_shas[name] = sha

                await asyncio.gather(*[_create_blob(n, c) for n, c in files.items()])

                if len(blob_shas) == len(files):
                    tree_payload: dict[str, Any] = {
                        "tree": [
                            {"path": name, "mode": "100644", "type": "blob", "sha": sha}
                            for name, sha in blob_shas.items()
                        ]
                    }
                    if base_tree_sha:
                        tree_payload["base_tree"] = base_tree_sha

                    tree_resp = await client.post(
                        f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/trees",
                        headers=headers,
                        json=tree_payload,
                    )
                    if tree_resp.status_code in (200, 201):
                        new_tree_sha = tree_resp.json().get("sha")
                        if new_tree_sha:
                            commit_resp = await client.post(
                                f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/commits",
                                headers=headers,
                                json={
                                    "message": description
                                    or "Deploy solution by AI Solution Builder",
                                    "tree": new_tree_sha,
                                    "parents": [parent_commit_sha] if parent_commit_sha else [],
                                },
                            )
                            if commit_resp.status_code in (200, 201):
                                new_commit_sha = commit_resp.json().get("sha")
                                if new_commit_sha:
                                    up_resp = await patch_fn(
                                        f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/refs/heads/{default_branch}",
                                        headers=headers,
                                        json={"sha": new_commit_sha, "force": True},
                                    )
                                    if up_resp.status_code in (200, 201):
                                        atomic_success = True
            except Exception as e:
                logger.warning(
                    "Atomic Git Data API attempt hit exception, falling back to contents API: %s", e
                )

        # 4. Fallback: If atomic Git Data API was skipped or unavailable,
        # use Contents API with robust automatic 409/422 retry that always fetches fresh SHAs.
        if not atomic_success:
            existing_shas: dict[str, str] = {}
            try:
                tree_resp = await client.get(
                    f"{GH_API_BASE}/repos/{owner}/{repo_name}/git/trees/{default_branch}?recursive=1",
                    headers=headers,
                )
                if tree_resp.status_code == 200:
                    existing_shas = {
                        item["path"]: item["sha"]
                        for item in tree_resp.json().get("tree", [])
                        if item.get("type") == "blob"
                    }
            except Exception:
                pass

            semaphore_contents = asyncio.Semaphore(4)
            remaining = {name: content for name, content in files.items() if name != "README.md"}

            async def _push_single_file(name: str, content: str) -> None:
                async with semaphore_contents:
                    path = f"{GH_API_BASE}/repos/{owner}/{repo_name}/contents/{name}"
                    payload: dict[str, Any] = {
                        "message": f"Deploy {name}",
                        "content": _b64(content.encode("utf-8")),
                        "branch": default_branch,
                    }
                    if name in existing_shas:
                        payload["sha"] = existing_shas[name]

                    resp = await client.put(path, headers=headers, json=payload)
                    # When 409 conflict or 422 occurs, query the exact current SHA and retry
                    if resp.status_code in (409, 422):
                        cur = await client.get(
                            path, headers=headers, params={"ref": default_branch}
                        )
                        if cur.status_code == 200:
                            payload["sha"] = cur.json().get("sha")
                            resp = await client.put(path, headers=headers, json=payload)
                        elif "is at " in resp.text:
                            import re

                            m = re.search(r"is at ([0-9a-f]{40})", resp.text)
                            if m:
                                payload["sha"] = m.group(1)
                                resp = await client.put(path, headers=headers, json=payload)

                    if resp.status_code not in (200, 201):
                        raise DeployError(
                            f"Push of {name} failed ({resp.status_code}): {resp.text[:300]}"
                        )

            await asyncio.gather(*[_push_single_file(n, c) for n, c in remaining.items()])

        repo_url = f"https://github.com/{owner}/{repo_name}"
        clone_url = f"https://github.com/{owner}/{repo_name}.git"
        logger.info("Deployed %s -> %s (%d files)", repo_name, repo_url, len(files))
        return {"url": repo_url, "clone_url": clone_url, "owner": owner, "branch": default_branch}


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")
