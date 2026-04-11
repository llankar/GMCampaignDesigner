"""Regression tests for campaign graph navigation selectors."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


class _DummyFrame:
    def __init__(self, *args, **kwargs):
        """Initialize the _DummyFrame instance."""
        self._children = []
        self._destroyed = False
        self._configured = {}
        if args:
            parent = args[0]
            if hasattr(parent, "_children"):
                parent._children.append(self)

    def after_idle(self, callback, *args, **kwargs):
        """Handle after idle."""
        return callback(*args, **kwargs)

    def grid(self, *args, **kwargs):
        """Handle grid."""
        return None

    def pack(self, *args, **kwargs):
        """Pack the operation."""
        return None

    def grid(self, *args, **kwargs):
        """Handle grid."""
        return None

    def bind(self, *args, **kwargs):
        """Bind the operation."""
        return None

    def configure(self, *args, **kwargs):
        """Handle configure."""
        self._configured.update(kwargs)

    def set(self, *args, **kwargs):
        """Handle scrollbar set."""
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        """Handle grid columnconfigure."""
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        """Handle grid rowconfigure."""
        return None

    def grid_propagate(self, *args, **kwargs):
        """Handle grid propagate."""
        return None

    def winfo_children(self):
        """Handle winfo children."""
        return [child for child in self._children if not getattr(child, "_destroyed", False)]

    def destroy(self):
        """Destroy the operation."""
        self._destroyed = True


class _FakeCanvas:
    def __init__(self, *args, **kwargs):
        """Initialize the _FakeCanvas instance."""
        self.bound = {}
        self.configured = {}
        self.window = None
        self.text_calls = []

    def pack(self, *args, **kwargs):
        """Pack the operation."""
        return None

    def bind(self, *args, **kwargs):
        """Bind the operation."""
        return None

    def create_window(self, _coords, *, window, anchor):
        """Create window."""
        self.window = window
        return "window-item"

    def delete(self, *args, **kwargs):
        """Delete the operation."""
        return None

    def create_rectangle(self, *args, **kwargs):
        """Create rectangle."""
        return "rectangle-item"

    def create_text(self, *args, **kwargs):
        """Create text."""
        self.text_calls.append(kwargs.get("text", ""))
        return f"text-item-{len(self.text_calls)}"

    def tag_bind(self, *args, **kwargs):
        """Bind a tag."""
        return None

    def configure(self, **kwargs):
        """Handle configure."""
        self.configured.update(kwargs)

    def grid(self, *args, **kwargs):
        """Handle grid."""
        return None

    def xview(self, *args, **kwargs):
        """Handle xview."""
        return (0.0, 1.0)

    def bbox(self, *args, **kwargs):
        """Handle bbox."""
        return (0, 0, 100, 100)

    def itemconfigure(self, *args, **kwargs):
        """Handle itemconfigure."""
        return None

    def winfo_exists(self):
        """Handle winfo exists."""
        return True

    def winfo_width(self):
        """Handle winfo width."""
        return 640

    def winfo_height(self):
        """Handle winfo height."""
        return 124


sys.modules["customtkinter"] = types.SimpleNamespace(
    CTkFrame=_DummyFrame,
    CTkScrollbar=_DummyFrame,
    CTkLabel=_DummyFrame,
    CTkFont=lambda *args, **kwargs: None,
)
sys.modules["modules.scenarios.gm_screen.dashboard.styles.dashboard_theme"] = types.SimpleNamespace(
    DASHBOARD_THEME=types.SimpleNamespace(
        panel_alt_bg="#111111",
        button_fg="#222222",
        panel_bg="#333333",
        accent_soft="#444444",
        card_border="#555555",
        text_primary="#ffffff",
        text_secondary="#cccccc",
    )
)

MODULE_PATH = Path("modules/campaigns/ui/graphical_display/components/navigation.py")
spec = importlib.util.spec_from_file_location("modules.campaigns.ui.graphical_display.components.navigation", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _make_scenario(title: str):
    return types.SimpleNamespace(title=title)


def test_scenario_selector_strip_updates_selection_without_rebuild(monkeypatch):
    """Verify that selection changes restyle existing cards without rebuilding them."""
    fake_canvas = _FakeCanvas()
    monkeypatch.setattr(module.tk, "Canvas", lambda *args, **kwargs: fake_canvas)

    strip = module.ScenarioSelectorStrip(
        _DummyFrame(),
        scenarios=[_make_scenario("Moonlit Wake"), _make_scenario("Catacomb Chase")],
        selected_index=0,
        on_select=lambda *_args: None,
    )

    initial_child_ids = [id(child) for child in strip.inner.winfo_children()]

    strip.set_selected_index(1)

    assert [id(child) for child in strip.inner.winfo_children()] == initial_child_ids
    assert strip._selected_index == 1
    assert strip._title_labels[1]._configured["text_color"] == "#f8fbff"
    assert strip._title_labels[0]._configured["text_color"] == module.DASHBOARD_THEME.text_primary


def test_scenario_selector_strip_only_rebuilds_when_scenarios_change(monkeypatch):
    """Verify that the scenario strip rebuilds only when the arc scenario list changes."""
    fake_canvas = _FakeCanvas()
    monkeypatch.setattr(module.tk, "Canvas", lambda *args, **kwargs: fake_canvas)

    strip = module.ScenarioSelectorStrip(
        _DummyFrame(),
        scenarios=[_make_scenario("Moonlit Wake"), _make_scenario("Catacomb Chase")],
        selected_index=0,
        on_select=lambda *_args: None,
    )

    initial_child_ids = [id(child) for child in strip.inner.winfo_children()]

    strip.set_scenarios([_make_scenario("Moonlit Wake"), _make_scenario("Catacomb Chase")], 1)
    assert [id(child) for child in strip.inner.winfo_children()] == initial_child_ids
    assert strip._selected_index == 1

    strip.set_scenarios([_make_scenario("Moonlit Wake"), _make_scenario("The Last Door")], 1)
    rebuilt_child_ids = [id(child) for child in strip.inner.winfo_children()]

    assert rebuilt_child_ids != initial_child_ids
    assert len(rebuilt_child_ids) == 2


def test_arc_selector_strip_renders_clean_separator(monkeypatch):
    """Verify that the arc selector uses a real bullet separator in the subtitle."""
    fake_canvas = _FakeCanvas()
    monkeypatch.setattr(module.tk, "Canvas", lambda *args, **kwargs: fake_canvas)

    module.ArcSelectorStrip(
        _DummyFrame(),
        arcs=[types.SimpleNamespace(name="PharmaCorp Protection & Espionage", status="Planned", scenarios=[1, 2, 3])],
        selected_index=0,
        on_select=lambda *_args: None,
    )

    assert any(text == "PharmaCorp Protection..." for text in fake_canvas.text_calls)
    assert any(text == "Planned • 3 scenarios" for text in fake_canvas.text_calls)


def test_arc_selector_truncation_helpers_emit_ascii_ellipsis():
    """Verify that truncation helpers never emit mojibake ellipsis glyphs."""
    title = "PharmaCorp Protection & Espionage"

    assert module._truncate(title, 24) == "PharmaCorp Protection..."
    assert module._truncate_middle(title, 24) == "PharmaCorp...& Espionage"
    assert "â" not in module._truncate(title, 24)
    assert "â" not in module._truncate_middle(title, 24)
    assert len(module._truncate(title, 24)) <= 24
    assert len(module._truncate_middle(title, 24)) <= 24
