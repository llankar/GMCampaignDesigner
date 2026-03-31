"""Helpers for campaign Status field widgets in the generic editor."""

from modules.campaigns.shared.arc_status import CANONICAL_ARC_STATUSES, canonicalize_arc_status


CAMPAIGN_STATUS_FIELD_NAME = "Status"
CAMPAIGN_ENTITY_SLUG = "campaigns"


def is_campaign_status_field(*, entity_type: str, field_name: str) -> bool:
    """Return whether campaign status field."""
    return (entity_type or "").strip().lower() == CAMPAIGN_ENTITY_SLUG and field_name == CAMPAIGN_STATUS_FIELD_NAME


def campaign_status_choices() -> list[str]:
    """Handle campaign status choices."""
    return list(CANONICAL_ARC_STATUSES)


def canonical_campaign_status(raw_value: object) -> str:
    """Handle canonical campaign status."""
    return canonicalize_arc_status(raw_value)
