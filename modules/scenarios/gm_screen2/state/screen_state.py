"""Mutable UI state container for GM Screen 2."""

from __future__ import annotations

from dataclasses import dataclass, field

from modules.scenarios.gm_screen2.domain.models import PanelPayload, ScenarioFilter, ScenarioSummary
from modules.scenarios.gm_screen2.state.layout_state import LayoutState


@dataclass(slots=True)
class ScreenState:
    """Single source of truth for GM Screen 2 UI state."""

    active_scenario: ScenarioSummary | None = None
    selected_panel_id: str = "overview"
    filters: ScenarioFilter = field(default_factory=ScenarioFilter)
    panel_payloads: dict[str, PanelPayload] = field(default_factory=dict)
    pinned_blocks: list[str] = field(default_factory=list)
    layout: LayoutState = field(default_factory=LayoutState)

    def set_active_scenario(self, scenario: ScenarioSummary | None) -> None:
        """Set active scenario and reset panel focus when needed."""
        self.active_scenario = scenario
        if scenario is None:
            self.panel_payloads.clear()
            self.selected_panel_id = "overview"

    def update_payloads(self, payloads: dict[str, PanelPayload]) -> None:
        """Replace panel payload map."""
        self.panel_payloads = dict(payloads)
        if self.selected_panel_id not in self.panel_payloads and self.panel_payloads:
            self.selected_panel_id = next(iter(self.panel_payloads))
