"""Onboarding scenarios focused on first-time GM core actions."""

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


def build_new_gm_mvp_steps() -> list[TourStep]:
    """Quickstart path aligned with the real campaign wizard controls."""
    return [
        TourStep(
            id="new_gm_mvp.open_campaign_builder",
            screen=OPEN_WIZARD.screen,
            target_widget_key=OPEN_WIZARD.widget_key,
            title="Open Campaign Builder",
            description=OPEN_WIZARD.expected_user_action,
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="new_gm_mvp.enter_campaign_name",
            screen=ENTER_CAMPAIGN_NAME.screen,
            target_widget_key=ENTER_CAMPAIGN_NAME.widget_key,
            title="Enter Campaign Name",
            description=ENTER_CAMPAIGN_NAME.expected_user_action,
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="new_gm_mvp.go_to_arcs",
            screen=GO_TO_ARCS.screen,
            target_widget_key=GO_TO_ARCS.widget_key,
            title="Continue to arcs",
            description=GO_TO_ARCS.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_mvp.go_to_review",
            screen=GO_TO_REVIEW.screen,
            target_widget_key=GO_TO_REVIEW.widget_key,
            title="Continue to review",
            description=GO_TO_REVIEW.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_mvp.save_campaign",
            screen=FINALIZE_CAMPAIGN.screen,
            target_widget_key=FINALIZE_CAMPAIGN.widget_key,
            title="Finalize",
            description=FINALIZE_CAMPAIGN.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
    ]


def build_new_gm_advanced_steps() -> list[TourStep]:
    """Extended quickstart using only controls that exist in the wizard."""
    return [
        TourStep(
            id="new_gm_advanced.open_campaign_builder",
            screen=OPEN_WIZARD.screen,
            target_widget_key=OPEN_WIZARD.widget_key,
            title="Open Campaign Builder",
            description=OPEN_WIZARD.expected_user_action,
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="new_gm_advanced.enter_campaign_name",
            screen=ENTER_CAMPAIGN_NAME.screen,
            target_widget_key=ENTER_CAMPAIGN_NAME.widget_key,
            title="Step 1: Campaign Name",
            description=ENTER_CAMPAIGN_NAME.expected_user_action,
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="new_gm_advanced.next_to_arcs",
            screen=GO_TO_ARCS.screen,
            target_widget_key=GO_TO_ARCS.widget_key,
            title="Go to step 2",
            description=GO_TO_ARCS.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.manage_arcs_optional",
            screen=MANAGE_ARCS_OPTIONAL.screen,
            target_widget_key=MANAGE_ARCS_OPTIONAL.widget_key,
            title="Step 2: Arcs (optional)",
            description=MANAGE_ARCS_OPTIONAL.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.next_to_review",
            screen=GO_TO_REVIEW.screen,
            target_widget_key=GO_TO_REVIEW.widget_key,
            title="Go to step 3",
            description=GO_TO_REVIEW.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.save_campaign",
            screen=FINALIZE_CAMPAIGN.screen,
            target_widget_key=FINALIZE_CAMPAIGN.widget_key,
            title="Final action",
            description=FINALIZE_CAMPAIGN.expected_user_action,
            placement=TourPlacement.LEFT,
        ),
    ]
