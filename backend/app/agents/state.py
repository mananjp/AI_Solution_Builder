"""
AI Solution Builder — Discovery State

TypedDict that flows through the LangGraph multi-agent pipeline.
Every agent node reads from and writes to this shared state.
"""

from typing import Any, TypedDict


class ModuleRecommendation(TypedDict):
    module: str
    reason: str


class ArtifactOutput(TypedDict):
    artifact_type: str
    title: str
    content: dict[str, Any]
    content_text: str


class DiscoveryState(TypedDict, total=False):
    """Shared state across all LangGraph agent nodes."""

    # ── User Input ───────────────────────────────
    user_message: str
    uploaded_context: str  # Parsed document/URL content
    conversation_history: list[dict[str, Any]]  # [{role, content}, ...]

    # ── Business Analysis ────────────────────────
    business_description: str
    industry: str
    business_size: str
    business_stage: str
    stakeholders: list[str]
    pain_points: list[str]
    confidence_score: float  # 0.0–1.0
    identified_solutions: list[str]
    clarification_questions: list[str]

    # ── Recommendation (for undirected users) ────
    recommended_modules: list[ModuleRecommendation]
    requires_confirmation: bool
    confirmed_modules: list[str]

    # ── Generated Artifacts ──────────────────────
    hld: ArtifactOutput | None
    lld: ArtifactOutput | None
    wireframes: list[ArtifactOutput] | None
    er_diagram: ArtifactOutput | None
    api_spec: ArtifactOutput | None
    database_schema: ArtifactOutput | None
    bpmn_flows: list[ArtifactOutput] | None
    roadmap: ArtifactOutput | None

    # ── Workable System (Section 5) ───────────────
    generated_schema: ArtifactOutput | None  # executable DDL + declarative JSON
    workable_modules: list[dict[str, Any]] | None  # module manifests for headless REST engine
    code_manifest: dict[str, Any] | None  # ZIP-ready file tree
    workable_ready: bool

    # ── Pipeline Control ─────────────────────────
    current_agent: str
    agent_messages: list[dict[str, Any]]  # Streaming messages for the frontend
    error: str | None
    status: str  # discovery, analyzing, recommending, generating, complete, error
