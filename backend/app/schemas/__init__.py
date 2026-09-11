"""
AI Solution Builder — Pydantic Schemas

Request/response models for all API endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

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
    created_at: datetime

    class Config:
        from_attributes = True


# ── Organization ──────────────────────────────────


class OrgResponse(BaseModel):
    id: UUID
    name: str
    credits_remaining: int
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
