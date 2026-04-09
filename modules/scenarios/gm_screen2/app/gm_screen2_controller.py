"""GM Screen 2 application controller (composition and lifecycle orchestration)."""

from __future__ import annotations

from modules.scenarios.gm_screen2.app.docking_controller import DockingController
from modules.scenarios.gm_screen2.events.contracts import EventBus
from modules.scenarios.gm_screen2.services.interfaces import PanelPayloadProvider, ScenarioRepository
from modules.scenarios.gm_screen2.state.screen_state import ScreenState


class GMScreen2Controller:
    """Coordinates state, data adapters, and passive UI view."""

    def __init__(
        self,
        scenario_repository: ScenarioRepository,
        panel_payload_provider: PanelPayloadProvider,
        state: ScreenState | None = None,
        events: EventBus | None = None,
    ) -> None:
        self._scenario_repository = scenario_repository
        self._panel_payload_provider = panel_payload_provider
        self.state = state or ScreenState()
        self.events = events or EventBus()
        self.docking = DockingController(self.state.layout, self.events)
        self._initialized = False

    def initialize(self) -> list:
        """Prepare controller and return available scenarios."""
        self._initialized = True
        scenarios = self._scenario_repository.list_scenarios(self.state.filters)
        self.events.publish("state_changed", {"action": "initialize"})
        return scenarios

    def load_scenario(self, scenario_id: str) -> None:
        """Load one scenario and its panel payloads into mutable state."""
        scenario = self._scenario_repository.get_scenario(scenario_id)
        self.state.set_active_scenario(scenario)
        if scenario is None:
            self.events.publish("state_changed", {"action": "load_scenario"})
            return
        payloads = self._panel_payload_provider.load_panel_payloads(scenario)
        self.state.update_payloads(payloads)
        self.events.publish("state_changed", {"action": "load_scenario"})

    def update_state(self, **changes) -> None:
        """Apply state updates in a controlled manner."""
        if "selected_panel_id" in changes:
            self.state.selected_panel_id = str(changes["selected_panel_id"])
        if "pinned_blocks" in changes:
            self.state.pinned_blocks = list(changes["pinned_blocks"])
        if "filters" in changes:
            self.state.filters = changes["filters"]
        self.events.publish("state_changed", {"action": "update_state"})

    def teardown(self) -> None:
        """Release all listeners and reset initialization state."""
        self.events.clear()
        self._initialized = False
