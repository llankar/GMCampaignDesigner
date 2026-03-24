from __future__ import annotations

import importlib


CRITICAL_MODULES = [
    "campaign_generator",
    "main_window",
    "modules.scenarios.gm_screen_view",
    "modules.maps.controllers.display_map_controller",
    "modules.maps.views.web_display_view",
]


def test_critical_modules_import_smoke() -> None:
    for module_name in CRITICAL_MODULES:
        module = importlib.import_module(module_name)
        assert module is not None, f"failed to import {module_name}"
