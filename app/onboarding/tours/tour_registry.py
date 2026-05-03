"""Central tour builder registry."""

from __future__ import annotations

from collections.abc import Callable

from app.onboarding.tour_models import TourStep

from .campaign_setup_tour import build_campaign_setup_steps
from .new_gm_quickstart_tour import (
    build_new_gm_advanced_steps,
    build_new_gm_mvp_steps,
)

TourBuilder = Callable[[], list[TourStep]]

TOUR_BUILDERS: dict[str, TourBuilder] = {
    "campaign_setup": build_campaign_setup_steps,
    "new_gm_mvp": build_new_gm_mvp_steps,
    "new_gm_advanced": build_new_gm_advanced_steps,
}


def build_tour_registry() -> dict[str, list[TourStep]]:
    """Build concrete tour steps from registered builders."""
    return {tour_id: builder() for tour_id, builder in TOUR_BUILDERS.items()}
