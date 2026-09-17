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
    # Render limit is typically 32 characters for service name slugs
    return clean[:30]


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

    async def deploy_repo(
        self,
        repo_url: str,
        repo_name: str,
        branch: str = "main",
        dockerfile_path: str = "./backend/Dockerfile",
        docker_context: str = "./backend",
    ) -> dict[str, Any]:
        """Create a new Web Service on Render for the specified repository.

        Returns a dictionary with:
          - service_id: str | None
          - service_url: str | None (e.g. https://xxx.onrender.com)
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
                "dashboard_url": None,
                "deploy_url": deploy_portal_url,
                "status": "pending_connection",
                "message": str(err),
            }

        service_name = clean_service_name(repo_name)
        payload = {
            "type": "web_service",
            "name": service_name,
            "ownerId": owner_id,
            "repo": repo_url,
            "branch": branch,
            "autoDeploy": "yes",
            "serviceDetails": {
                "runtime": "docker",
                "envSpecificDetails": {
                    "dockerfilePath": dockerfile_path,
                    "dockerContext": docker_context,
                },
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{RENDER_API_BASE}/services",
                headers=self._headers,
                json=payload,
            )

            if resp.status_code in (200, 201):
                res_data = resp.json()
                service = res_data.get("service", {})
                service_id = service.get("id")
                service_details = service.get("serviceDetails", {})
                service_url = service_details.get("url")
                dashboard_url = service.get("dashboardUrl")

                logger.info(
                    "Render service created: %s (%s) -> %s",
                    service_name,
                    service_id,
                    service_url,
                )
                return {
                    "service_id": service_id,
                    "service_url": service_url,
                    "dashboard_url": dashboard_url,
                    "deploy_url": deploy_portal_url,
                    "status": "deployed",
                    "message": "Service successfully provisioned on Render.",
                }

            # If creation fails (e.g. 400 with repo access required or name conflict),
            # provide a clear explanatory message with 1-click fallback.
            error_body = resp.text[:400]
            logger.warning(
                "Render service create returned HTTP %d: %s", resp.status_code, error_body
            )
            return {
                "service_id": None,
                "service_url": None,
                "dashboard_url": None,
                "deploy_url": deploy_portal_url,
                "status": "pending_connection",
                "message": f"Render API responded HTTP {resp.status_code}: {error_body}",
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
