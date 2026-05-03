"""Onboarding scenarios focused on first-time GM core actions."""

from __future__ import annotations

from app.onboarding.tour_models import TourPlacement, TourStep

from .tour_i18n_fr import NEW_GM_ADVANCED_TEXTS, NEW_GM_MVP_TEXTS


def build_new_gm_mvp_steps() -> list[TourStep]:
    """5-step MVP quickstart for a new GM."""
    return [
        TourStep(
            id="new_gm_mvp.create_campaign",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title=NEW_GM_MVP_TEXTS["create_campaign_title"],
            description=NEW_GM_MVP_TEXTS["create_campaign_description"],
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="new_gm_mvp.name_campaign",
            screen="campaign_builder",
            target_widget_key="input_campaign_name",
            title=NEW_GM_MVP_TEXTS["name_campaign_title"],
            description=NEW_GM_MVP_TEXTS["name_campaign_description"],
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="new_gm_mvp.hands_on",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_MVP_TEXTS["hands_on_title"],
            description=NEW_GM_MVP_TEXTS["hands_on_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_mvp.first_scene",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_MVP_TEXTS["first_scene_title"],
            description=NEW_GM_MVP_TEXTS["first_scene_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_mvp.summary",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title=NEW_GM_MVP_TEXTS["summary_title"],
            description=NEW_GM_MVP_TEXTS["summary_description"],
            placement=TourPlacement.RIGHT,
        ),
    ]


def build_new_gm_advanced_steps() -> list[TourStep]:
    """8-step advanced path with planning and review habits."""
    return [
        TourStep(
            id="new_gm_advanced.create_campaign",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title=NEW_GM_ADVANCED_TEXTS["create_campaign_title"],
            description=NEW_GM_ADVANCED_TEXTS["create_campaign_description"],
            placement=TourPlacement.RIGHT,
        ),
        TourStep(
            id="new_gm_advanced.name_campaign",
            screen="campaign_builder",
            target_widget_key="input_campaign_name",
            title=NEW_GM_ADVANCED_TEXTS["name_campaign_title"],
            description=NEW_GM_ADVANCED_TEXTS["name_campaign_description"],
            placement=TourPlacement.BOTTOM,
        ),
        TourStep(
            id="new_gm_advanced.hands_on",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_ADVANCED_TEXTS["hands_on_title"],
            description=NEW_GM_ADVANCED_TEXTS["hands_on_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.create_scene",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_ADVANCED_TEXTS["create_scene_title"],
            description=NEW_GM_ADVANCED_TEXTS["create_scene_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.add_npc",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_ADVANCED_TEXTS["add_npc_title"],
            description=NEW_GM_ADVANCED_TEXTS["add_npc_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.link_clue",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_ADVANCED_TEXTS["link_clue_title"],
            description=NEW_GM_ADVANCED_TEXTS["link_clue_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.review_checklist",
            screen="campaign_builder",
            target_widget_key="btn_create_campaign",
            title=NEW_GM_ADVANCED_TEXTS["review_checklist_title"],
            description=NEW_GM_ADVANCED_TEXTS["review_checklist_description"],
            placement=TourPlacement.LEFT,
        ),
        TourStep(
            id="new_gm_advanced.summary",
            screen="main_window",
            target_widget_key="btn_new_campaign",
            title=NEW_GM_ADVANCED_TEXTS["summary_title"],
            description=NEW_GM_ADVANCED_TEXTS["summary_description"],
            placement=TourPlacement.RIGHT,
        ),
    ]
