from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .persistence import CampaignConfigRepository


@dataclass(slots=True)
class CampaignOverviewSelectionState:
    arc_name: str = ""
    scenario_title: str = ""


class CampaignOverviewSelectionStore:
    """Persists campaign overview focus state in a dedicated metadata table."""

    def __init__(self, repository: CampaignConfigRepository | None = None):
        self._repository = repository or CampaignConfigRepository()

    def load(self, campaign_record: dict[str, Any] | None) -> CampaignOverviewSelectionState:
        if not isinstance(campaign_record, dict):
            return CampaignOverviewSelectionState()

        campaign_name = str(campaign_record.get("Name") or "").strip()
        if not campaign_name:
            return CampaignOverviewSelectionState()

        stored_arc_name, stored_scenario_title = self._repository.load_overview_focus(campaign_name)
        if stored_arc_name or stored_scenario_title:
            return CampaignOverviewSelectionState(
                arc_name=stored_arc_name,
                scenario_title=stored_scenario_title,
            )
        return CampaignOverviewSelectionState()

    def save(self, campaign_record: dict[str, Any] | None, *, arc_name: str, scenario_title: str) -> dict[str, Any] | None:
        if not isinstance(campaign_record, dict):
            return campaign_record

        campaign_name = str(campaign_record.get("Name") or "").strip()
        if not campaign_name:
            return campaign_record

        self._repository.save_overview_focus(
            campaign_name,
            arc_name=str(arc_name or "").strip(),
            scenario_title=str(scenario_title or "").strip(),
        )
        return campaign_record
