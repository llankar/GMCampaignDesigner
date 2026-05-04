"""Canonical contract for campaign-creation tour steps.

Update this file first whenever the campaign builder flow changes.
Tour builders should consume these constants so widget targets and action copy
stay synchronized with real controls.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CampaignCreationTourAnchor:
    """Single, reusable definition for a campaign-creation tour stop."""

    screen: str
    widget_key: str
    expected_user_action: str


OPEN_WIZARD = CampaignCreationTourAnchor(
    screen="main_window",
    widget_key="btn_new_campaign",
    expected_user_action='Click "New campaign" to open the Campaign Builder Wizard.',
)

ENTER_CAMPAIGN_NAME = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="input_campaign_name",
    expected_user_action='In "Campaign Foundation", enter a value in "Campaign Name" (required).',
)

GO_TO_ARCS = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_wizard_next",
    expected_user_action='Click "Next" to continue to the arcs step.',
)

MANAGE_ARCS_OPTIONAL = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_add_arc",
    expected_user_action='Use "+ New Arc" only if you want to add or edit arcs. This is optional for saving the campaign.',
)

GO_TO_REVIEW = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_wizard_next",
    expected_user_action='Click "Next" to open step 3 (Review).',
)

FINALIZE_CAMPAIGN = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_finalize_campaign",
    expected_user_action='On the Review step, click "Save Campaign" to finalize.',
)
