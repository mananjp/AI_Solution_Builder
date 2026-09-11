"""
AI Solution Builder — Models Package

Imports all ORM models so Alembic and the app can discover them.
"""

from app.models.artifact import ArtifactComment, SolutionArtifact
from app.models.audit import AuditLog
from app.models.context import ContextChunk
from app.models.credit import CreditTransaction, Plan
from app.models.organization import Organization
from app.models.recommendation import RecommendationEvent
from app.models.solution import Solution
from app.models.user import User
from app.models.workable import WorkableSchema
from app.models.workspace import Workspace

__all__ = [
    "User",
    "Organization",
    "Workspace",
    "Solution",
    "SolutionArtifact",
    "ArtifactComment",
    "Plan",
    "CreditTransaction",
    "RecommendationEvent",
    "AuditLog",
    "WorkableSchema",
    "ContextChunk",
]
