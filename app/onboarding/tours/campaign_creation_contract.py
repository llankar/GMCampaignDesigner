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

ENTER_CAMPAIGN_LOGLINE = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="input_campaign_logline",
    expected_user_action="Add a one-sentence logline so arcs and scenarios have a clear premise.",
)

ENTER_CAMPAIGN_OBJECTIVE = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="input_campaign_objective",
    expected_user_action="Write the main objective the players will pursue across the campaign.",
)

GO_TO_ARCS = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_wizard_next",
    expected_user_action='Click "Next" to continue to the arcs step.',
)

MANAGE_ARCS_OPTIONAL = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_add_arc",
    expected_user_action='Click "+ New Arc" to create the first story arc for this campaign.',
)

ENTER_ARC_NAME = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="input_arc_name",
    expected_user_action="Name the arc. Use a short label that you will recognize later in the campaign overview.",
)

ENTER_ARC_SUMMARY = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="input_arc_summary",
    expected_user_action="Summarize what changes during this arc: threat, opportunity, or mystery.",
)

ENTER_ARC_OBJECTIVE = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="input_arc_objective",
    expected_user_action="Write the objective that makes the arc playable at the table.",
)

CREATE_SCENARIO_FOR_ARC = CampaignCreationTourAnchor(
    screen="campaign_builder",
    widget_key="btn_create_scenario_for_arc",
    expected_user_action='Click "Create Scenario for selected arc" to build and link the first scenario.',
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
