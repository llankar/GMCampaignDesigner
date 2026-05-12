"""Helpers for campaign Status field widgets in the generic editor."""

from modules.campaigns.shared.arc_status import CANONICAL_PROGRESS_STATUSES, canonicalize_progress_status


CAMPAIGN_STATUS_FIELD_NAME = "Status"
CAMPAIGN_ENTITY_SLUG = "campaigns"
SCENARIO_ENTITY_SLUG = "scenarios"


def is_campaign_status_field(*, entity_type: str, field_name: str) -> bool:
    """Return whether campaign status field."""
    return (entity_type or "").strip().lower() == CAMPAIGN_ENTITY_SLUG and field_name == CAMPAIGN_STATUS_FIELD_NAME


def is_campaign_or_scenario_status_field(*, entity_type: str, field_name: str) -> bool:
    """Return whether the field uses the shared campaign progress status values."""
    entity_slug = (entity_type or "").strip().lower()
    return entity_slug in {CAMPAIGN_ENTITY_SLUG, SCENARIO_ENTITY_SLUG} and field_name == CAMPAIGN_STATUS_FIELD_NAME


def campaign_status_choices() -> list[str]:
    """Handle campaign status choices."""
    return list(CANONICAL_PROGRESS_STATUSES)


def canonical_campaign_status(raw_value: object) -> str:
    """Handle canonical campaign status."""
    return canonicalize_progress_status(raw_value)
