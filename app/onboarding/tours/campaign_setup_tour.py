"""Onboarding steps for the campaign setup flow."""

from __future__ import annotations

from app.onboarding.tour_models import TourPlacement, TourStep

from .tour_i18n_en import CAMPAIGN_SETUP_TEXTS


def build_campaign_setup_steps() -> list[TourStep]:
    """Return an immutable definition of steps for the campaign setup tour."""
    return [
        TourStep(
            id="campaign_setup.open_wizard",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title=CAMPAIGN_SETUP_TEXTS["welcome_title"],
            description=CAMPAIGN_SETUP_TEXTS["welcome_description"],
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="campaign_setup.name",
            screen="campaign_builder",
            target_widget_key="input_campaign_name",
            title=CAMPAIGN_SETUP_TEXTS["name_title"],
            description=CAMPAIGN_SETUP_TEXTS["name_description"],
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="campaign_setup.finish",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=CAMPAIGN_SETUP_TEXTS["finish_title"],
            description=CAMPAIGN_SETUP_TEXTS["finish_description"],
            placement=TourPlacement.LEFT,
        ),
    ]
