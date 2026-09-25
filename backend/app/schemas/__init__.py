"""
AI Solution Builder — Pydantic Schemas

Request/response models for all API endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# ── Ingestion ──────────────────────────────────────


class UrlParseRequest(BaseModel):
    """Payload to fetch a website URL and extract its readable text."""

    url: str = Field(..., min_length=1, max_length=2048)


# ── Auth ──────────────────────────────────────────


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    org_name: str = Field(..., min_length=2, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    org_id: UUID | None = None
    auth_provider: str = "local"
    is_anonymous: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class SocialProvidersResponse(BaseModel):
    """List of fully configured social OAuth providers and anonymous auth status."""

    providers: list[str] = Field(default_factory=list)
    allow_anonymous: bool = True


class AnonymousAuthResponse(BaseModel):
    """Token response returned when creating a throwaway demo identity."""

    access_token: str
    token_type: str = "bearer"
    is_anonymous: bool = True
    credits_remaining: int | None = None
    user: UserResponse


class UpgradeAnonymousRequest(BaseModel):
    """Converts a temporary anonymous account to a permanent registered account."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    org_name: str | None = None


class UserSettingsUpdate(BaseModel):
    """Profile settings used for deployments (tokens kept server-side only)."""

    github_token: str | None = Field(None, min_length=1, max_length=1000)
    render_api_key: str | None = Field(None, min_length=1, max_length=1000)
    vercel_token: str | None = Field(None, min_length=1, max_length=1000)


# ── Organization ──────────────────────────────────


class OrgResponse(BaseModel):
    id: UUID
    name: str
    credits_remaining: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Workspace ─────────────────────────────────────


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class WorkspaceResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    solution_count: int = 0

    class Config:
        from_attributes = True


# ── Solution ──────────────────────────────────────


class SolutionCreate(BaseModel):
    workspace_id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None


class SolutionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    description: str | None
    status: str
    approval_status: str | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SolutionDetailResponse(SolutionResponse):
    ai_state: dict[str, Any] | None = None
    conversation_history: list[dict[str, Any]] | None = None
    artifacts: list["ArtifactResponse"] = []


# ── Artifact ──────────────────────────────────────


class ArtifactResponse(BaseModel):
    id: UUID
    solution_id: UUID
    artifact_type: str
    title: str
    content: dict[str, Any]
    content_text: str | None
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactRegenerateRequest(BaseModel):
    feedback: str = Field(..., min_length=1)


# ── Chat ──────────────────────────────────────────


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1)
    solution_id: UUID
    uploaded_context: str | None = None  # Parsed document content


class ChatStreamEvent(BaseModel):
    event: str  # agent_start, agent_progress, agent_complete, message, error
    agent: str | None = None
    data: Any = None


# ── Recommendation ────────────────────────────────


class ModuleRecommendation(BaseModel):
    module: str
    reason: str


class RecommendationResponse(BaseModel):
    industry: str
    modules: list[ModuleRecommendation]
    requires_confirmation: bool = True


class RecommendationConfirm(BaseModel):
    solution_id: UUID
    accepted_modules: list[str]


# ── Workable (System Runtime) ─────────────────────


class ProvisionRequest(BaseModel):
    """Payload to trigger provisioning of a solution's workable schema."""

    force: bool = False


# ── OpenCode MVP Builder ────────────────────────


class MVPBuildRequest(BaseModel):
    """Payload to trigger an OpenCode MVP build for a solution."""

    app_name: str | None = Field(None, min_length=1, max_length=255)
    template: str | None = Field(None, min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    force: bool = False


class MVPQuickBuildRequest(BaseModel):
    """Payload to trigger an instant MVP build from a premade template."""

    template: str = Field(..., min_length=1, max_length=64)
    app_name: str | None = Field(None, min_length=1, max_length=255)
    config: dict[str, Any] = Field(default_factory=dict)


class OpenCodeChatRequest(BaseModel):
    """Payload to chat directly with OpenCode."""

    message: str = Field(..., min_length=1)
    session_id: str | None = None
    solution_id: UUID | None = None
    app_name: str | None = None
    uploaded_context: str | None = None
    build_requested: bool = False  # Finalize + verify the workspace into an MVPBuild


class MVPTemplateResponse(BaseModel):
    """A deployable starter template the user can pick as their project."""

    slug: str
    title: str
    description: str
    app_name: str
    industry: str


class MVPDeployRequest(BaseModel):
    """Payload to deploy a finished MVP build to GitHub (+ Render blueprint)."""

    repo_name: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    description: str = ""
    private: bool = False
    force: bool = False
    # Environment values the user confirmed before deploy. NEXT_PUBLIC_* keys go
    # to the frontend service; everything else goes to the backend service.
    env: dict[str, Any] = Field(default_factory=dict)


class MVPDeployStatusResponse(BaseModel):
    """Live deploy state for a build — polled by the UI every few seconds.

    Never claims the app is live based on the trigger itself; every status
    comes from the Render deploy objects.
    """

    overall: str = "building"  # queued | building | live | failed
    repo_url: str | None = None
    backend_url: str | None = None
    frontend_url: str | None = None
    deploy_url: str | None = None
    injected_env: dict[str, str] = Field(default_factory=dict)
    services: dict[str, Any] = Field(default_factory=dict)


class MVPEnvVarSpec(BaseModel):
    """A single environment variable the generated app needs (or may need)."""

    key: str
    required: bool = True  # True = must be provided before production deploy
    kind: str = "runtime"  # "build" (NEXT_PUBLIC_*) | "runtime" (server secret)
    description: str = ""
    default: str | None = None
    current: str | None = None  # value already known (saved env or auto-injected)
    auto_injected: bool = False  # set automatically (e.g. backend URL → frontend)
    occurrences: int = 0


class MVPEnvPlanResponse(BaseModel):
    """Env vars required/optional by a finished build, plus auto-injections."""

    env: list[MVPEnvVarSpec] = Field(default_factory=list)
    app_name: str | None = None
    # Service-to-service URLs the agent already knows (auto-injected on deploy).
    injected: dict[str, str] = Field(default_factory=dict)


class MVPFileEntry(BaseModel):
    """A single generated file in an MVP build workspace."""

    path: str
    size: int
    is_dir: bool = False


class MVPBuildResponse(BaseModel):
    build_id: UUID
    solution_id: UUID
    build_number: int
    status: str
    workspace_path: str
    file_count: int = 0
    error_message: str | None = None
    repo_url: str | None = None
    render_service_url: str | None = None
    frontend_url: str | None = None
    backend_url: str | None = None
    render_dashboard_url: str | None = None
    render_deploy_url: str | None = None
    render_deploy_status: str | None = None
    deploy_state: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None
    files: list[MVPFileEntry] = []


class MVPConfigUpdate(BaseModel):
    """Apply user-supplied configuration overlays to a finished build."""

    app_name: str | None = None
    env: dict[str, Any] = Field(default_factory=dict)
