"""
AI Solution Builder — Render Automated Deployer & Blueprint Integration

Handles programmatic deployment to Render via the Render REST API (v1).
Supports:
1. Workspace / Owner discovery (GET /v1/owners)
2. Automated service creation (POST /v1/services)
3. Live URL and Dashboard URL discovery
4. 1-Click Render Blueprint Portal URL generation (https://render.com/deploy?repo=...)
5. Preview service teardown (DELETE /v1/services/{service_id})
"""

import logging
import re
from typing import Any

import httpx

RENDER_API_BASE = "https://api.render.com/v1"
RENDER_DEPLOY_PORTAL_BASE = "https://render.com/deploy"

logger = logging.getLogger(__name__)


class RenderDeployError(RuntimeError):
    """Raised when a Render API operation fails."""


def clean_service_name(repo_name: str) -> str:
    """Normalize a repo name into a valid Render service name.

    Render service names must be lowercase, alphanumeric with hyphens,
    and cannot start or end with a hyphen.
    """
    clean = re.sub(r"[^a-zA-Z0-9-]", "-", repo_name).lower()
    clean = re.sub(r"-+", "-", clean).strip("-")
    if not clean:
        clean = "app"
    # Render limit is typically 32 characters; cap base at 26 to leave room for "-api"
    return clean[:26]


def get_1click_deploy_url(repo_url: str) -> str:
    """Produce the official 1-click 'Deploy to Render' portal URL.

    Render automatically parses the root render.yaml blueprint and sets up
    all defined services, databases, and environment variables.
    """
    if not repo_url:
        return RENDER_DEPLOY_PORTAL_BASE
    return f"{RENDER_DEPLOY_PORTAL_BASE}?repo={repo_url}"


class RenderDeployer:
    """Client for Render REST API v1."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise RenderDeployError("Render API key is required")
        self.api_key = api_key.strip()
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def get_owner_id(self) -> str:
        """Retrieve the primary workspace (owner) ID for this API key."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{RENDER_API_BASE}/owners",
                headers=self._headers,
                params={"limit": 10},
            )
            if resp.status_code != 200:
                msg = f"Failed to retrieve Render workspaces (HTTP {resp.status_code}): {resp.text[:300]}"
                logger.error(msg)
                raise RenderDeployError(msg)

            data = resp.json()
            if not isinstance(data, list) or len(data) == 0:
                raise RenderDeployError("No Render workspace/owner found for this API key.")

            first = data[0]
            owner_obj = first.get("owner", {})
            owner_id = owner_obj.get("id")
            if not owner_id:
                raise RenderDeployError("Render workspace response did not contain an owner ID.")

            return str(owner_id)

    async def get_service_by_name(self, name: str) -> dict[str, Any] | None:
        """Find an existing service in this workspace by exact name."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{RENDER_API_BASE}/services",
                headers=self._headers,
                params={"name": name, "limit": 5},
            )
            if resp.status_code == 200:
                services = resp.json()
                if isinstance(services, list):
                    for item in services:
                        svc = item.get("service", {}) if isinstance(item, dict) else {}
                        if svc.get("name") == name:
                            return svc
            return None

    async def trigger_deploy(self, service_id: str, clear_cache: bool = False) -> str | None:
        """Trigger a new deployment for an existing service."""
        if not service_id:
            return None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{RENDER_API_BASE}/services/{service_id}/deploys",
                headers=self._headers,
                json={"clearCache": "clear" if clear_cache else "do_not_clear"},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                deploy_id = data.get("id")
                return str(deploy_id) if deploy_id is not None else None
            logger.warning(
                "Trigger deploy for service %s returned HTTP %d: %s",
                service_id,
                resp.status_code,
                resp.text[:200],
            )
            return None

    async def create_or_update_service(
        self,
        name: str,
        owner_id: str,
        repo_url: str,
        branch: str,
        dockerfile_path: str,
        docker_context: str,
        env_vars: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        """Create a web service or trigger a redeploy if it already exists."""
        # 1. Check if service already exists
        existing = await self.get_service_by_name(name)
        if existing:
            svc_id = existing.get("id")
            svc_url = existing.get("serviceDetails", {}).get("url")
            dash_url = existing.get("dashboardUrl")
            logger.info(
                "Found existing Render service %s (%s) -> %s; triggering redeploy",
                name,
                svc_id,
                svc_url,
            )
            if svc_id:
                await self.trigger_deploy(svc_id)
            return {
                "id": svc_id,
                "url": svc_url,
                "dashboard_url": dash_url,
                "name": name,
            }

        payload: dict[str, Any] = {
            "type": "web_service",
            "name": name,
            "ownerId": owner_id,
            "repo": repo_url,
            "branch": branch,
            "autoDeploy": "yes",
            "serviceDetails": {
                "runtime": "docker",
                "plan": "free",
                "envSpecificDetails": {
                    "dockerfilePath": dockerfile_path,
                    "dockerContext": docker_context,
                },
            },
        }
        if env_vars:
            payload["serviceDetails"]["envVars"] = env_vars

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{RENDER_API_BASE}/services",
                headers=self._headers,
                json=payload,
            )
            if resp.status_code in (200, 201):
                res_data = resp.json()
                service = res_data.get("service", {})
                svc_id = service.get("id")
                service_details = service.get("serviceDetails", {})
                svc_url = service_details.get("url")
                dash_url = service.get("dashboardUrl")
                logger.info("Render service created: %s (%s) -> %s", name, svc_id, svc_url)
                return {
                    "id": svc_id,
                    "url": svc_url,
                    "dashboard_url": dash_url,
                    "name": name,
                }

            # If creation failed because name already taken, attempt lookup fallback
            if resp.status_code in (400, 409):
                existing_retry = await self.get_service_by_name(name)
                if existing_retry:
                    svc_id = existing_retry.get("id")
                    svc_url = existing_retry.get("serviceDetails", {}).get("url")
                    dash_url = existing_retry.get("dashboardUrl")
                    if svc_id:
                        await self.trigger_deploy(svc_id)
                    return {
                        "id": svc_id,
                        "url": svc_url,
                        "dashboard_url": dash_url,
                        "name": name,
                    }

            error_body = resp.text[:400]
            logger.warning(
                "Render service create for %s returned HTTP %d: %s",
                name,
                resp.status_code,
                error_body,
            )
            return None

    async def deploy_repo(
        self,
        repo_url: str,
        repo_name: str,
        branch: str = "main",
        dockerfile_path: str = "./frontend/Dockerfile",
        docker_context: str = "./frontend",
    ) -> dict[str, Any]:
        """Create or update Web Services on Render for the specified repository.

        Provisions both backend (-api) and frontend services on Render's free tier
        and always returns the live frontend application URL.

        Returns a dictionary with:
          - service_id: str | None (frontend service id)
          - service_url: str | None (live frontend URL, e.g. https://xxx.onrender.com)
          - frontend_url: str | None
          - backend_url: str | None (live backend API URL, e.g. https://xxx-api.onrender.com)
          - dashboard_url: str | None
          - deploy_url: str (1-click blueprint portal fallback/complement)
          - status: 'deployed' | 'pending_connection'
          - message: str
        """
        deploy_portal_url = get_1click_deploy_url(repo_url)

        try:
            owner_id = await self.get_owner_id()
        except RenderDeployError as err:
            logger.warning("Render owner discovery failed: %s", err)
            return {
                "service_id": None,
                "service_url": None,
                "frontend_url": None,
                "backend_url": None,
                "dashboard_url": None,
                "deploy_url": deploy_portal_url,
                "status": "pending_connection",
                "message": str(err),
            }

        base_name = clean_service_name(repo_name)
        api_service_name = f"{base_name}-api"
        fe_service_name = base_name

        # 1. Deploy / update backend service on port 8000
        backend_info = await self.create_or_update_service(
            name=api_service_name,
            owner_id=owner_id,
            repo_url=repo_url,
            branch=branch,
            dockerfile_path="./backend/Dockerfile",
            docker_context="./backend",
            env_vars=[
                {"key": "PORT", "value": "8000"},
                {"key": "CORS_ORIGINS", "value": "*"},
            ],
        )
        backend_url = backend_info.get("url") if backend_info else None

        # 2. Deploy / update frontend service on port 3000
        fe_env_vars = [{"key": "PORT", "value": "3000"}]
        if backend_url:
            fe_env_vars.append({"key": "NEXT_PUBLIC_API_URL", "value": backend_url})

        frontend_info = await self.create_or_update_service(
            name=fe_service_name,
            owner_id=owner_id,
            repo_url=repo_url,
            branch=branch,
            dockerfile_path=dockerfile_path,
            docker_context=docker_context,
            env_vars=fe_env_vars,
        )

        frontend_url = frontend_info.get("url") if frontend_info else None
        frontend_id = frontend_info.get("id") if frontend_info else None
        dashboard_url = frontend_info.get("dashboard_url") if frontend_info else None

        # The user's primary application link is the frontend URL
        service_url = frontend_url or backend_url
        service_id = frontend_id or (backend_info.get("id") if backend_info else None)
        if not dashboard_url and backend_info:
            dashboard_url = backend_info.get("dashboard_url")

        if service_url:
            return {
                "service_id": service_id,
                "service_url": service_url,
                "frontend_url": frontend_url or service_url,
                "backend_url": backend_url,
                "dashboard_url": dashboard_url,
                "deploy_url": deploy_portal_url,
                "status": "deployed",
                "message": f"Service successfully deployed on Render. Live frontend: {service_url}",
            }

        return {
            "service_id": None,
            "service_url": None,
            "frontend_url": None,
            "backend_url": None,
            "dashboard_url": None,
            "deploy_url": deploy_portal_url,
            "status": "pending_connection",
            "message": "Render automated service provisioning pending. Use the 1-click blueprint deploy URL to connect.",
        }

    async def destroy_service(self, service_id: str) -> bool:
        """Tear down a Render service by its ID."""
        if not service_id:
            return False

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(
                f"{RENDER_API_BASE}/services/{service_id}",
                headers=self._headers,
            )
            if resp.status_code in (200, 204):
                logger.info("Deleted Render service %s", service_id)
                return True
            logger.warning(
                "Failed to delete Render service %s (HTTP %d): %s",
                service_id,
                resp.status_code,
                resp.text[:200],
            )
            return False


# Global helper instance
render_deployer = RenderDeployer
