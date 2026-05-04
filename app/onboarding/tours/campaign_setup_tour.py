"""Onboarding steps for the campaign setup flow."""

from __future__ import annotations

from app.onboarding.tour_models import TourPlacement, TourStep


def build_campaign_setup_steps() -> list[TourStep]:
    """Return an immutable definition of steps for the campaign setup tour."""
    return [
        TourStep(
            id="campaign_setup.open_wizard",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title="Open Campaign Builder",
            description="Click \"New campaign\" to open the Campaign Builder Wizard.",
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="campaign_setup.foundation_name",
            screen="campaign_builder",
            target_widget_key="input_campaign_name",
            title="Step 1: Campaign Name",
            description="In \"Campaign Foundation\", enter a value in \"Campaign Name\" (required).",
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="campaign_setup.foundation_next",
            screen="campaign_builder",
            target_widget_key="btn_wizard_next",
            title="Go to step 2",
            description="Click \"Next\" to continue to the arcs step.",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="campaign_setup.arcs_manage",
            screen="campaign_builder",
            target_widget_key="btn_add_arc",
            title="Step 2: Manage arcs (optional)",
            description="Use \"+ New Arc\" only if you want to add or edit arcs. This is optional for saving the campaign.",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="campaign_setup.arcs_next",
            screen="campaign_builder",
            target_widget_key="btn_wizard_next",
            title="Go to review",
            description="Click \"Next\" to open step 3 (Review).",
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="campaign_setup.review_finalize",
            screen="campaign_builder",
            target_widget_key="btn_save_campaign",
            title="Step 3: Final action",
            description="On the Review step, click \"Save Campaign\" to finalize.",
            placement=TourPlacement.LEFT,
        ),
    ]
