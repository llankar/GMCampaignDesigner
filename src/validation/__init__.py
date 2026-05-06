"""Validation package for cross-entity consistency checks."""

from .hierarchy_rules import (
    ALLOWED_HIERARCHY_CHILDREN,
    FIELD_EXPECTED_TYPES,
    format_hierarchy_context,
    format_parent_child_context,
)
from .issue_models import IssuePayload, IssueType, ValidationIssue
from .reference_validator import (
    EntityRecord,
    ReferenceRecord,
    ReferenceValidationResult,
    ReferenceValidatorConfig,
    validate_reference_graph,
    validate_references,
)

__all__ = [
    "ALLOWED_HIERARCHY_CHILDREN",
    "FIELD_EXPECTED_TYPES",
    "EntityRecord",
    "IssuePayload",
    "IssueType",
    "ReferenceRecord",
    "ReferenceValidationResult",
    "ReferenceValidatorConfig",
    "ValidationIssue",
    "format_hierarchy_context",
    "format_parent_child_context",
    "validate_reference_graph",
    "validate_references",
]
