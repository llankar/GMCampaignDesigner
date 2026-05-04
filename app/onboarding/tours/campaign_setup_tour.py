"""Onboarding steps for the campaign setup flow."""

from __future__ import annotations

from app.onboarding.tour_models import TourPlacement, TourStep

from .campaign_creation_contract import (
    ENTER_CAMPAIGN_NAME,
    FINALIZE_CAMPAIGN,
    GO_TO_ARCS,
    GO_TO_REVIEW,
    MANAGE_ARCS_OPTIONAL,
    OPEN_WIZARD,
)


def build_campaign_setup_steps() -> list[TourStep]:
    """Return an immutable definition of steps for the campaign setup tour."""
    return [
        TourStep(
            id="campaign_setup.open_wizard",
            screen=OPEN_WIZARD.screen,
            target_widget_key=OPEN_WIZARD.widget_key,
            title="Open Campaign Builder",
            description=OPEN_WIZARD.expected_user_action,
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="campaign_setup.foundation_name",
            screen=ENTER_CAMPAIGN_NAME.screen,
            target_widget_key=ENTER_CAMPAIGN_NAME.widget_key,
            title="Step 1: Campaign Name",
            description=ENTER_CAMPAIGN_NAME.expected_user_action,
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="campaign_setup.foundation_next",
            screen=GO_TO_ARCS.screen,
            target_widget_key=GO_TO_ARCS.widget_key,
            title="Go to step 2",
            description=GO_TO_ARCS.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="campaign_setup.arcs_manage",
            screen=MANAGE_ARCS_OPTIONAL.screen,
            target_widget_key=MANAGE_ARCS_OPTIONAL.widget_key,
            title="Step 2: Manage arcs (optional)",
            description=MANAGE_ARCS_OPTIONAL.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="campaign_setup.arcs_next",
            screen=GO_TO_REVIEW.screen,
            target_widget_key=GO_TO_REVIEW.widget_key,
            title="Go to review",
            description=GO_TO_REVIEW.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="campaign_setup.review_finalize",
            screen=FINALIZE_CAMPAIGN.screen,
            target_widget_key=FINALIZE_CAMPAIGN.widget_key,
            title="Step 3: Final action",
            description=FINALIZE_CAMPAIGN.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
    ]
