"""Regression tests for campaign status field."""

from modules.generic.editor.shared.campaign_status_field import (
    campaign_status_choices,
    canonical_campaign_status,
    is_campaign_status_field,
)


def test_campaign_status_field_detection():
    """Verify that campaign status field detection."""
    assert is_campaign_status_field(entity_type="campaigns", field_name="Status")
    assert is_campaign_status_field(entity_type=" Campaigns ", field_name="Status")
    assert not is_campaign_status_field(entity_type="events", field_name="Status")
    assert not is_campaign_status_field(entity_type="campaigns", field_name="State")


def test_campaign_status_canonicalization_and_choices():
    """Verify that campaign status canonicalization and choices."""
    assert canonical_campaign_status("running") == "In Progress"
    assert canonical_campaign_status("done") == "Completed"
    assert canonical_campaign_status("") == "Planned"
    assert campaign_status_choices() == ["Planned", "In Progress", "Paused", "Completed"]
