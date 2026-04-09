"""Compatibility desktop entrypoint for GM Screen 2."""

from __future__ import annotations

from modules.scenarios.gm_screen2.app.gm_screen2_controller import GMScreen2Controller
from modules.scenarios.gm_screen2.services import GenericModelScenarioRepository, ScenarioPanelPayloadProvider
from modules.scenarios.gm_screen2.ui.gm_screen2_root_view import GMScreen2RootView


class GMScreen2View(GMScreen2RootView):
    """Backwards-compatible class name mapped to the new root view architecture."""

    def __init__(self, master, *, scenario_wrapper, scenario_id: str | None = None, **kwargs):
        repository = GenericModelScenarioRepository(scenario_wrapper)
        provider = ScenarioPanelPayloadProvider(repository)
        controller = GMScreen2Controller(repository, provider)
        super().__init__(master, controller=controller, **kwargs)
        scenarios = controller.initialize()
        resolved_id = scenario_id or (scenarios[0].scenario_id if scenarios else None)
        if resolved_id:
            controller.load_scenario(resolved_id)
