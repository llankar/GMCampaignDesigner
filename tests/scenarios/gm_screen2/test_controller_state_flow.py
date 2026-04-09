"""State flow tests for GM Screen 2 controller."""

from modules.scenarios.gm_screen2.app.gm_screen2_controller import GMScreen2Controller
from modules.scenarios.gm_screen2.domain.models import PanelPayload, ScenarioSummary


class _RepoDouble:
    def __init__(self):
        self._scenario = ScenarioSummary(scenario_id="S1", title="Arrival", summary="Start")

    def list_scenarios(self, filters=None):
        return [self._scenario]

    def get_scenario(self, scenario_id: str):
        return self._scenario if scenario_id == "S1" else None


class _ProviderDouble:
    def load_panel_payloads(self, scenario: ScenarioSummary):
        return {
            "overview": PanelPayload(panel_id="overview", title=scenario.title, content_blocks=("A",)),
            "notes": PanelPayload(panel_id="notes", title="Notes", content_blocks=("B",)),
        }


def test_controller_initialize_and_load_updates_state():
    controller = GMScreen2Controller(_RepoDouble(), _ProviderDouble())

    scenarios = controller.initialize()
    assert [scenario.scenario_id for scenario in scenarios] == ["S1"]

    controller.load_scenario("S1")
    assert controller.state.active_scenario is not None
    assert controller.state.active_scenario.title == "Arrival"
    assert set(controller.state.panel_payloads) == {"overview", "notes"}


def test_controller_update_state_applies_mutable_fields():
    controller = GMScreen2Controller(_RepoDouble(), _ProviderDouble())
    controller.update_state(selected_panel_id="notes", split_ratios=[0.5, 0.3, 0.2], pinned_blocks=["hook"]) 

    assert controller.state.selected_panel_id == "notes"
    assert controller.state.layout.split_ratios == [0.5, 0.3, 0.2]
    assert controller.state.pinned_blocks == ["hook"]
