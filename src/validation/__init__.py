"""Validation package for cross-entity consistency checks."""

from .field_normalization import (
    FIELD_NORMALIZATION_RULES,
    FieldNormalizationRule,
    normalize_validator_reference_fields,
)
from .hierarchy_rules import (
    ALLOWED_HIERARCHY_CHILDREN,
    FIELD_EXPECTED_TYPES,
    format_hierarchy_context,
    format_parent_child_context,
)
from .issue_models import IssuePayload, IssueType, ValidationIssue
from .similarity_matcher import (
    SimilarityCandidate,
    SimilarityDecision,
    SimilarityMatch,
    SimilarityMatcherConfig,
    SimilarityMatchResult,
    classify_similarity_matches,
    coerce_similarity_candidate,
    match_reference,
    normalize_similarity_text,
    score_similarity,
)
from .reference_validator import (
    EntityRecord,
    ReferenceRecord,
    ReferenceTraversalDiagnostics,
    ReferenceValidationResult,
    ReferenceValidatorConfig,
    validate_reference_graph,
    validate_references,
)

__all__ = [
    "ALLOWED_HIERARCHY_CHILDREN",
    "FIELD_NORMALIZATION_RULES",
    "FIELD_EXPECTED_TYPES",
    "EntityRecord",
    "FieldNormalizationRule",
    "IssuePayload",
    "IssueType",
    "ReferenceRecord",
    "ReferenceTraversalDiagnostics",
    "ReferenceValidationResult",
    "ReferenceValidatorConfig",
    "score_similarity",
    "normalize_similarity_text",
    "match_reference",
    "coerce_similarity_candidate",
    "classify_similarity_matches",
    "SimilarityMatchResult",
    "SimilarityMatcherConfig",
    "SimilarityMatch",
    "SimilarityDecision",
    "SimilarityCandidate",
    "ValidationIssue",
    "normalize_validator_reference_fields",
    "format_hierarchy_context",
    "format_parent_child_context",
    "validate_reference_graph",
    "validate_references",
]
