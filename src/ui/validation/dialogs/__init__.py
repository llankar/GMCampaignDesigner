"""Validation dialogs."""

from .generic_editor_launcher import (
    GenericEditorCreationRequest,
    GenericEditorCreationResult,
    GenericEditorLauncher,
    build_prefilled_entity,
    creation_request_from_issue,
    entity_slug_for_expected_type,
)
from .ambiguous_reference_dialog import (
    AmbiguousReferenceCandidate,
    AmbiguousReferenceDialog,
    AmbiguousReferenceDialogConfig,
    open_ambiguous_reference_dialog,
)
from .campaign_selector_dialog import (
    CampaignSelectorDialog,
    CampaignSelectorOption,
    open_campaign_selector_dialog,
)
from .remap_target_selector_dialog import (
    RemapTargetOption,
    RemapTargetSelectorDialog,
    open_remap_target_selector_dialog,
)
from .missing_reference_dialog import (
    MissingReferenceDialog,
    MissingReferenceDialogConfig,
    open_missing_reference_dialog,
)
from .invalid_hierarchy_dialog import (
    InvalidHierarchyDialog,
    InvalidHierarchyDialogConfig,
    open_invalid_hierarchy_dialog,
)
from .validation_summary_dialog import (
    ValidationSummaryCounts,
    ValidationSummaryDialog,
    open_validation_summary_dialog,
)

__all__ = [
    "GenericEditorCreationRequest",
    "GenericEditorCreationResult",
    "GenericEditorLauncher",
    "CampaignSelectorDialog",
    "CampaignSelectorOption",
    "AmbiguousReferenceCandidate",
    "AmbiguousReferenceDialog",
    "AmbiguousReferenceDialogConfig",
    "InvalidHierarchyDialog",
    "InvalidHierarchyDialogConfig",
    "MissingReferenceDialog",
    "MissingReferenceDialogConfig",
    "RemapTargetOption",
    "RemapTargetSelectorDialog",
    "ValidationSummaryCounts",
    "ValidationSummaryDialog",
    "build_prefilled_entity",
    "creation_request_from_issue",
    "entity_slug_for_expected_type",
    "open_ambiguous_reference_dialog",
    "open_campaign_selector_dialog",
    "open_invalid_hierarchy_dialog",
    "open_missing_reference_dialog",
    "open_remap_target_selector_dialog",
    "open_validation_summary_dialog",
]
