"""
AI Solution Builder — Render Automated Deployer & Blueprint Integration

Handles programmatic deployment to Render via the Render REST API (v1).
Supports:
1. Workspace / Owner discovery (GET /v1/owners)
2. Automated service creation (POST /v1/services)
3. Live URL and Dashboard URL discovery
4. 1-Click Render Blueprint Portal URL generation (https://render.com/deploy?repo=...)
5. Preview service teardown (DELETE /v1/services/{service_id})
6. Deploy status polling (GET /v1/services/{service_id}/deploys/{deploy_id})
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
        """Trigger a new deployment for an existing service.

        Returns the deploy ID on success, which can be used to poll status.
        """
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

    # -- Deploy status inspection ------------------------------------------------

    # Render deploy statuses grouped for UI display
    _LIVE_STATUSES = {"live"}
    _FAILED_STATUSES = {"build_failed", "update_failed", "canceled", "pre_deploy_failed"}
    _BUILDING_STATUSES = {
        "created",
        "queued",
        "build_in_progress",
        "update_in_progress",
        "pre_deploy_in_progress",
    }

    async def get_deploy_status(
        self,
        service_id: str,
        deploy_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve the status of a specific deploy.

        Returns the full deploy object from Render, or None on failure.
        The ``status`` field will be one of: created, queued,
        build_in_progress, update_in_progress, live, deactivated,
        build_failed, update_failed, canceled, pre_deploy_in_progress,
        pre_deploy_failed.
        """
        if not service_id or not deploy_id:
            return None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{RENDER_API_BASE}/services/{service_id}/deploys/{deploy_id}",
                headers=self._headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return data
                return None
            logger.warning(
                "Deploy status for %s/%s returned HTTP %d",
                service_id,
                deploy_id,
                resp.status_code,
            )
            return None

    def _classify_render_status(self, raw: str) -> str:
        """Map a raw Render deploy status to a simplified UI status.

        Returns ``'live'``, ``'building'``, or ``'failed'``.
        """
        if raw in self._LIVE_STATUSES:
            return "live"
        if raw in self._FAILED_STATUSES:
            return "failed"
        return "building"

    async def check_deploy_status(
        self,
        service_id: str,
        deploy_id: str,
    ) -> str:
        """Single-shot deploy status check.

        Returns a simplified status: ``'building'``, ``'live'``, or ``'failed'``.
        Defaults to ``'building'`` if the API can't be reached.
        """
        deploy = await self.get_deploy_status(service_id, deploy_id)
        if deploy is None:
            return "building"
        return self._classify_render_status(deploy.get("status", "created"))

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
        """Create a web service or trigger a redeploy if it already exists.

        The returned dict now includes a ``deploy_id`` key (str | None) so
        callers can poll the deploy status via ``check_deploy_status()``.
        """
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
            deploy_id = None
            if svc_id:
                deploy_id = await self.trigger_deploy(svc_id)
            return {
                "id": svc_id,
                "url": svc_url,
                "dashboard_url": dash_url,
                "name": name,
                "deploy_id": deploy_id,
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
                # New services auto-deploy; capture the initial deploy ID
                initial_deploy_id: str | None = None
                deploys = res_data.get("deploys") or []
                if deploys and isinstance(deploys, list):
                    initial_deploy_id = deploys[0].get("id")
                logger.info("Render service created: %s (%s) -> %s", name, svc_id, svc_url)
                return {
                    "id": svc_id,
                    "url": svc_url,
                    "dashboard_url": dash_url,
                    "name": name,
                    "deploy_id": initial_deploy_id,
                }

            # If creation failed because name already taken, attempt lookup fallback
            if resp.status_code in (400, 409):
                existing_retry = await self.get_service_by_name(name)
                if existing_retry:
                    svc_id = existing_retry.get("id")
                    svc_url = existing_retry.get("serviceDetails", {}).get("url")
                    dash_url = existing_retry.get("dashboardUrl")
                    deploy_id = None
                    if svc_id:
                        deploy_id = await self.trigger_deploy(svc_id)
                    return {
                        "id": svc_id,
                        "url": svc_url,
                        "dashboard_url": dash_url,
                        "name": name,
                        "deploy_id": deploy_id,
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
        dockerfile_path: str = "./Dockerfile",
        docker_context: str = ".",
        backend_env_vars: list[dict[str, str]] | None = None,
        frontend_env_vars: list[dict[str, str]] | None = None,
        unified: bool = True,
    ) -> dict[str, Any]:
        """Create or update Web Services on Render for the specified repository.

        When ``unified=True`` (default), provisions a single unified web service
        (FastAPI backend + Next.js frontend in one container), eliminating
        chicken-and-egg deployment ordering, CORS latency, and NEXT_PUBLIC_API_URL
        build-time baking issues.

        When ``unified=False``, deploys in staged 2-service order for legacy
        scaffolds.

        Returns a dictionary with:
          - services: {web/backend/frontend: {...}} each with
            name, service_id, deploy_id, url, dashboard_url, status
          - service_id / service_url / frontend_url / backend_url
          - dashboard_url / deploy_url / status / render_deploy_status
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
                "render_deploy_status": "failed",
                "services": {},
                "message": str(err),
            }

        base_name = clean_service_name(repo_name)
        unknown: dict[str, Any] = {
            "service_id": None,
            "deploy_id": None,
            "url": None,
            "dashboard_url": None,
            "status": "failed",
        }

        if unified:
            # ── Unified single-container deployment ──────────────────────────
            env_map: dict[str, str] = {
                "PORT": "3000",
                "CORS_ORIGINS": "*",
            }
            for ev in backend_env_vars or []:
                if ev.get("key"):
                    env_map[ev["key"]] = ev.get("value", "")
            for ev in frontend_env_vars or []:
                if ev.get("key") and ev["key"] != "NEXT_PUBLIC_API_URL":
                    env_map[ev["key"]] = ev.get("value", "")

            combined_env_vars = [{"key": k, "value": v} for k, v in env_map.items()]

            web_info = await self.create_or_update_service(
                name=base_name,
                owner_id=owner_id,
                repo_url=repo_url,
                branch=branch,
                dockerfile_path=dockerfile_path,
                docker_context=docker_context,
                env_vars=combined_env_vars,
            )

            web_url = web_info.get("url") if web_info else None
            web_services: dict[str, Any] = {
                **unknown,
                "name": base_name,
            }
            if web_info:
                web_services.update(
                    {
                        "service_id": web_info.get("id"),
                        "deploy_id": web_info.get("deploy_id"),
                        "url": web_url,
                        "dashboard_url": web_info.get("dashboard_url"),
                        "status": "building",
                    }
                )

            services = {
                "web": web_services,
                "frontend": web_services,
                "backend": web_services,
            }
            service_id = web_services.get("service_id")
            dashboard_url = web_services.get("dashboard_url")

            if web_url or web_info:
                return {
                    "services": services,
                    "service_id": service_id,
                    "service_url": web_url,
                    "frontend_url": web_url,
                    "backend_url": web_url,
                    "dashboard_url": dashboard_url,
                    "deploy_url": deploy_portal_url,
                    "status": "deploying",
                    "render_deploy_status": "building",
                    "message": (
                        "Unified full-stack web application is being provisioned on Render as a "
                        "single container service; live status is streamed by the deploy status endpoint."
                    ),
                }

        # ── Legacy 2-service deployment fallback ─────────────────────────────
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
                *(backend_env_vars or []),
            ],
        )
        backend_url = backend_info.get("url") if backend_info else None
        backend_services: dict[str, Any] = {
            **unknown,
            "name": api_service_name,
        }
        if backend_info:
            backend_services.update(
                {
                    "service_id": backend_info.get("id"),
                    "deploy_id": backend_info.get("deploy_id"),
                    "url": backend_url,
                    "dashboard_url": backend_info.get("dashboard_url"),
                    "status": "building",
                }
            )

        # 2. Deploy / update frontend service on port 3000
        fe_env_vars = [{"key": "PORT", "value": "3000"}]
        if backend_url:
            fe_env_vars.append({"key": "NEXT_PUBLIC_API_URL", "value": backend_url})
        for ev in frontend_env_vars or []:
            if ev not in fe_env_vars:
                fe_env_vars.append(ev)

        frontend_info = await self.create_or_update_service(
            name=fe_service_name,
            owner_id=owner_id,
            repo_url=repo_url,
            branch=branch,
            dockerfile_path="./frontend/Dockerfile" if dockerfile_path == "./Dockerfile" else dockerfile_path,
            docker_context="./frontend" if docker_context == "." else docker_context,
            env_vars=fe_env_vars,
        )
        frontend_url = frontend_info.get("url") if frontend_info else None
        frontend_services: dict[str, Any] = {
            **unknown,
            "name": fe_service_name,
        }
        if frontend_info:
            frontend_services.update(
                {
                    "service_id": frontend_info.get("id"),
                    "deploy_id": frontend_info.get("deploy_id"),
                    "url": frontend_url,
                    "dashboard_url": frontend_info.get("dashboard_url"),
                    "status": "building",
                }
            )

        services = {"backend": backend_services, "frontend": frontend_services}
        service_url = frontend_url or backend_url
        service_id = frontend_services.get("service_id") or backend_services.get("service_id")
        dashboard_url = (
            frontend_services.get("dashboard_url")
            or backend_services.get("dashboard_url")
        )

        if service_url or (frontend_info or backend_info):
            return {
                "services": services,
                "service_id": service_id,
                "service_url": service_url,
                "frontend_url": frontend_url or service_url,
                "backend_url": backend_url,
                "dashboard_url": dashboard_url,
                "deploy_url": deploy_portal_url,
                "status": "deploying",
                "render_deploy_status": "building",
                "message": (
                    "Deployments are being provisioned on Render. Backend is deployed "
                    "first so the frontend picks up its URL automatically; live status "
                    "is streamed by the deploy status endpoint."
                ),
            }

        return {
            "services": services,
            "service_id": None,
            "service_url": None,
            "frontend_url": None,
            "backend_url": None,
            "dashboard_url": None,
            "deploy_url": deploy_portal_url,
            "status": "pending_connection",
            "render_deploy_status": "failed",
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
