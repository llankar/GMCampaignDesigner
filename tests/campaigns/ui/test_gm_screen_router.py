"""Regression tests for GM screen router."""

import importlib.util
import sys
from pathlib import Path


module_path = Path("modules/campaigns/ui/graphical_display/services/gm_screen_router.py")
spec = importlib.util.spec_from_file_location("test_gm_screen_router_module", module_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
open_scenario_in_embedded_gm_screen = module.open_scenario_in_embedded_gm_screen


class _HostWithGM:
    def __init__(self):
        """Initialize the _HostWithGM instance."""
        self.calls = []

    def open_gm_screen(self, **kwargs):
        """Open GM screen."""
        self.calls.append(kwargs)


class _Widget:
    def __init__(self, host):
        """Initialize the _Widget instance."""
        self._host = host

    def winfo_toplevel(self):
        """Handle winfo toplevel."""
        return self._host


def test_router_prefers_embedded_gm_screen():
    """Verify that router prefers embedded GM screen."""
    host = _HostWithGM()
    widget = _Widget(host)
    fallback_calls = []

    open_scenario_in_embedded_gm_screen(widget, "Night Run", fallback=lambda: fallback_calls.append(True))

    assert host.calls == [{"show_empty_message": True, "scenario_name": "Night Run"}]
    assert fallback_calls == []


def test_router_falls_back_without_host_api():
    """Verify that router falls back without host API."""
    widget = _Widget(object())
    fallback_calls = []

    open_scenario_in_embedded_gm_screen(widget, "Night Run", fallback=lambda: fallback_calls.append(True))

    assert fallback_calls == [True]
