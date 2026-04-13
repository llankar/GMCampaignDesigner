"""Workspace layout behavior tests for the GM Table."""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from modules.scenarios.gm_table.workspace import (
    PANEL_MARGIN,
    GMTablePanel,
    GMTableWorkspace,
    PanelDefinition,
    _resize_geometry,
)


class _FakePanel:
    def __init__(self, width: int, height: int, *, x: int = 0, y: int = 0) -> None:
        self._width = width
        self._height = height
        self.x = x
        self.y = y
        self.definition = SimpleNamespace(state={})
        self._layout_mode = "floating"
        self._restore_geometry = None
        self.focused = False
        self.lifted = False

    @property
    def layout_mode(self) -> str:
        return self._layout_mode

    def winfo_x(self) -> int:
        return self.x

    def winfo_y(self) -> int:
        return self.y

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height

    def _set_size(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def geometry_snapshot(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self._width, "height": self._height}

    def place_configure(self, *, x: int | None = None, y: int | None = None, width: int | None = None, height: int | None = None) -> None:
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if width is not None:
            self._width = width
        if height is not None:
            self._height = height

    def apply_geometry(self, geometry: dict[str, int]) -> None:
        self.place_configure(
            x=geometry["x"],
            y=geometry["y"],
            width=geometry["width"],
            height=geometry["height"],
        )

    def enter_layout_mode(self, mode: str, geometry: dict[str, int]) -> None:
        if mode != "floating" and self._layout_mode == "floating":
            self._restore_geometry = self.geometry_snapshot()
        self._layout_mode = mode
        self.apply_geometry(geometry)

    def restore_layout(self, **_kwargs) -> bool:
        if self._restore_geometry is None:
            return False
        self._layout_mode = "floating"
        self.apply_geometry(self._restore_geometry)
        return True

    def clear_layout_mode(self) -> None:
        self._layout_mode = "floating"

    def set_focus_state(self, focused: bool) -> None:
        self.focused = focused

    def lift(self) -> None:
        self.lifted = True


def test_auto_arrange_preserves_large_scenario_panel_geometry() -> None:
    """Arrange should not shrink scenario/entity panels below their useful size."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {
        "scenario-panel": _FakePanel(920, 680),
        "note-panel": _FakePanel(520, 360),
    }
    workspace._definitions = {
        "scenario-panel": PanelDefinition(
            panel_id="scenario-panel",
            kind="entity",
            title="Scenario: Night Run",
            state={"entity_type": "Scenarios", "entity_name": "Night Run"},
        ),
        "note-panel": PanelDefinition(
            panel_id="note-panel",
            kind="note",
            title="Session Notes",
            state={},
        ),
    }
    workspace._z_order = ["scenario-panel", "note-panel"]
    workspace.surface = SimpleNamespace(
        winfo_width=lambda: 1300,
        winfo_height=lambda: 900,
    )
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None

    GMTableWorkspace.auto_arrange(workspace)

    scenario_panel = workspace._panels["scenario-panel"]
    note_panel = workspace._panels["note-panel"]

    assert scenario_panel.winfo_width() == 920
    assert scenario_panel.winfo_height() == 680
    assert note_panel.y > scenario_panel.y


def test_snap_panel_tiles_two_panels_side_by_side() -> None:
    """Snapping one panel left should place the next panel on the right half."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {
        "notes": _FakePanel(520, 360, x=40, y=32),
        "map": _FakePanel(860, 620, x=420, y=48),
    }
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
        "map": PanelDefinition(panel_id="map", kind="world_map", title="World Map", state={}),
    }
    workspace._z_order = ["map", "notes"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1400, winfo_height=lambda: 900)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None

    GMTableWorkspace.snap_panel(workspace, "notes", "left")

    notes = workspace._panels["notes"]
    world_map = workspace._panels["map"]

    assert notes.layout_mode == "left"
    assert world_map.layout_mode == "right"
    assert notes.x == PANEL_MARGIN
    assert world_map.x > notes.x
    assert notes.winfo_width() == world_map.winfo_width()
    assert notes.winfo_height() == world_map.winfo_height()


def test_toggle_panel_maximize_restores_previous_geometry() -> None:
    """Header maximize should restore the prior floating geometry on the next toggle."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {"notes": _FakePanel(520, 360, x=84, y=56)}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._z_order = ["notes"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1400, winfo_height=lambda: 900)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None

    GMTableWorkspace.toggle_panel_maximize(workspace, "notes")
    panel = workspace._panels["notes"]

    assert panel.layout_mode == "maximize"
    assert panel.x == PANEL_MARGIN
    assert panel.y == PANEL_MARGIN
    assert panel.winfo_width() == 1400 - (PANEL_MARGIN * 2)

    GMTableWorkspace.toggle_panel_maximize(workspace, "notes")

    assert panel.layout_mode == "floating"
    assert panel.x == 84
    assert panel.y == 56
    assert panel.winfo_width() == 520
    assert panel.winfo_height() == 360


def test_resize_geometry_supports_dragging_from_top_left_corner() -> None:
    """Edge resizing should grow and reposition the panel when dragging the north-west corner."""
    geometry = _resize_geometry(
        "nw",
        start_geometry={"x": 260, "y": 220, "width": 420, "height": 320},
        delta_x=-120,
        delta_y=-80,
        surface_w=1400,
        surface_h=900,
        min_width=GMTablePanel.MIN_WIDTH,
        min_height=GMTablePanel.MIN_HEIGHT,
    )

    assert geometry["x"] == 140
    assert geometry["y"] == 140
    assert geometry["width"] == 540
    assert geometry["height"] == 400


def test_clamp_panels_reflows_maximized_panel_when_surface_changes() -> None:
    """Docked panels should stay docked when the GM Table itself is resized."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    panel = _FakePanel(520, 360, x=84, y=56)
    panel.enter_layout_mode("maximize", {"x": 12, "y": 12, "width": 1376, "height": 876})
    workspace._panels = {"notes": panel}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._z_order = ["notes"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1180, winfo_height=lambda: 760)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None

    GMTableWorkspace.clamp_panels(workspace)

    assert panel.layout_mode == "maximize"
    assert panel.x == PANEL_MARGIN
    assert panel.y == PANEL_MARGIN
    assert panel.winfo_width() == 1180 - (PANEL_MARGIN * 2)
    assert panel.winfo_height() == 760 - (PANEL_MARGIN * 2)


def test_mount_payload_widget_grids_direct_child_widget() -> None:
    """Widget payloads returned directly by builders should be mounted automatically."""
    root = tk.Tk()
    root.withdraw()
    try:
        workspace = GMTableWorkspace.__new__(GMTableWorkspace)
        host = tk.Frame(root)
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        payload = tk.Frame(host)

        GMTableWorkspace._mount_payload_widget(workspace, host, payload)

        assert payload.winfo_manager() == "grid"
        assert int(payload.grid_info()["row"]) == 0
        assert int(payload.grid_info()["column"]) == 0
        assert payload.grid_info()["sticky"] == "nesw"
    finally:
        root.destroy()


def test_mount_payload_widget_preserves_existing_geometry_manager() -> None:
    """The workspace should not remount payload widgets that are already managed."""
    root = tk.Tk()
    root.withdraw()
    try:
        workspace = GMTableWorkspace.__new__(GMTableWorkspace)
        host = tk.Frame(root)
        payload = tk.Frame(host)
        payload.pack(fill="both", expand=True)

        GMTableWorkspace._mount_payload_widget(workspace, host, payload)

        assert payload.winfo_manager() == "pack"
    finally:
        root.destroy()
