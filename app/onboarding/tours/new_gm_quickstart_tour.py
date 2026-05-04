"""Onboarding scenarios focused on first-time GM core actions."""

from __future__ import annotations

from app.onboarding.tour_models import TourPlacement, TourStep


def build_new_gm_mvp_steps() -> list[TourStep]:
    """Quickstart path aligned with the real campaign wizard controls."""
    return [
        TourStep(
            id="new_gm_mvp.open_campaign_builder",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title="Open Campaign Builder",
            description="Click \"New campaign\".",
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="new_gm_mvp.enter_campaign_name",
            screen="campaign_builder",
            target_widget_key="input_campaign_name",
            title="Enter Campaign Name",
            description="In step 1, fill \"Campaign Name\" (required).",
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="new_gm_mvp.go_to_arcs",
            screen="campaign_builder",
            target_widget_key="btn_wizard_next",
            title="Continue to arcs",
            description="Click \"Next\".",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_mvp.go_to_review",
            screen="campaign_builder",
            target_widget_key="btn_wizard_next",
            title="Continue to review",
            description="On step 2, click \"Next\" to open \"Review\".",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_mvp.save_campaign",
            screen="campaign_builder",
            target_widget_key="btn_save_campaign",
            title="Finalize",
            description="Click \"Save Campaign\".",
            placement=TourPlacement.LEFT,
        ),
    ]


def build_new_gm_advanced_steps() -> list[TourStep]:
    """Extended quickstart using only controls that exist in the wizard."""
    return [
        TourStep(
            id="new_gm_advanced.open_campaign_builder",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title="Open Campaign Builder",
            description="Click \"New campaign\".",
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="new_gm_advanced.enter_campaign_name",
            screen="campaign_builder",
            target_widget_key="input_campaign_name",
            title="Step 1: Campaign Name",
            description="Fill \"Campaign Name\" before leaving step 1.",
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="new_gm_advanced.next_to_arcs",
            screen="campaign_builder",
            target_widget_key="btn_wizard_next",
            title="Go to step 2",
            description="Click \"Next\".",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.manage_arcs_optional",
            screen="campaign_builder",
            target_widget_key="btn_add_arc",
            title="Step 2: Arcs (optional)",
            description="Use \"+ New Arc\" only if you want to manage arcs now.",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.next_to_review",
            screen="campaign_builder",
            target_widget_key="btn_wizard_next",
            title="Go to step 3",
            description="Click \"Next\" to open the review step.",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.save_campaign",
            screen="campaign_builder",
            target_widget_key="btn_save_campaign",
            title="Final action",
            description="Click \"Save Campaign\" to finish.",
            placement=TourPlacement.LEFT,
        ),
    ]
