"""
AI Solution Builder — Pydantic Schemas for Legacy Repository Modernization
"""

from typing import Any

from pydantic import BaseModel, Field


class LegacyRepoAnalyzeRequest(BaseModel):
    github_repo_url: str | None = Field(
        None,
        description="Public or private GitHub repository URL (e.g. https://github.com/org/repo)",
    )
    github_token: str | None = Field(None, description="Optional GitHub Personal Access Token")
    local_path: str | None = Field(None, description="Local repository path on disk")


class CredentialValidateRequest(BaseModel):
    key_name: str = Field(..., description="Name of credential (e.g. GROQ_API_KEY, OPENAI_API_KEY)")
    key_value: str = Field(..., description="Secret value to validate")


class CredentialValidateResponse(BaseModel):
    key_name: str
    format_valid: bool
    connection_tested: bool
    connection_success: bool
    message: str
    masked_key: str


class ModernizeRequest(BaseModel):
    local_path: str | None = Field(None, description="Local path to repository")
    github_repo_url: str | None = Field(None, description="GitHub repository URL")
    github_token: str | None = Field(None, description="Optional GitHub Personal Access Token")
    requested_features: list[str] = Field(
        default_factory=lambda: ["ai_chatbot"], description="Features to add"
    )
    credentials: dict[str, str] = Field(
        default_factory=dict, description="Dictionary of API credentials"
    )


class ModernizeResponse(BaseModel):
    status: str
    build_id: str
    target_repository: str
    detected_stack: dict[str, Any]
    credentials_configured: dict[str, str]
    modified_files: list[str]
    modernized: list[str]
    added_features: list[str]
    preserved_features: list[str]
    validation: dict[str, Any]
    schedule_summary: dict[str, Any]
    sutra_os: str
    git: dict[str, str]
    zip_size_bytes: int
