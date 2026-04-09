"""Reducer behavior tests for GM Screen 2 docking actions."""

from modules.scenarios.gm_screen2.app.gm_screen2_controller import GMScreen2Controller
from modules.scenarios.gm_screen2.domain.models import PanelPayload, PanelSection, PanelItem, ScenarioSummary
from modules.scenarios.gm_screen2.state.layout_reducer import find_split, find_zone


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
            "overview": PanelPayload(panel_id="overview", title=scenario.title, sections=(PanelSection("A", (PanelItem(text="A"),)),)),
            "notes": PanelPayload(panel_id="notes", title="Notes", sections=(PanelSection("B", (PanelItem(text="B"),)),)),
        }


def test_docking_split_resize_and_move_actions_mutate_layout_tree():
    controller = GMScreen2Controller(_RepoDouble(), _ProviderDouble())

    controller.docking.split_zone("zone_mid", "vertical", "zone_extra", moved_panel_id="notes")
    assert find_zone(controller.state.layout.root, "zone_extra") is not None

    controller.docking.resize_split("split_zone_mid_zone_extra", 0.7)
    assert round(find_split(controller.state.layout.root, "split_zone_mid_zone_extra").ratio, 2) == 0.7

    controller.docking.move_panel("overview", "zone_extra")
    assert "overview" in find_zone(controller.state.layout.root, "zone_extra").panel_stack
