"""
AI Solution Builder — Legacy Repository Understanding & Modernization Suite
"""

from app.services.legacy_repo.analyzer import LegacyRepoAnalyzer
from app.services.legacy_repo.boundary import assert_safe_boundary, is_path_safe
from app.services.legacy_repo.conflict_graph import ConflictGraphScheduler, TaskWorkstream
from app.services.legacy_repo.credentials import CredentialValidator
from app.services.legacy_repo.feature_extension import FeatureExtensionEngine
from app.services.legacy_repo.modernizer import LegacyRepoModernizer
from app.services.legacy_repo.validator import LegacyRepoValidator

__all__ = [
    "assert_safe_boundary",
    "is_path_safe",
    "LegacyRepoAnalyzer",
    "CredentialValidator",
    "ConflictGraphScheduler",
    "TaskWorkstream",
    "FeatureExtensionEngine",
    "LegacyRepoModernizer",
    "LegacyRepoValidator",
]
