"""Workspace layout behavior tests for the GM Table."""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from modules.scenarios.gm_table.workspace import GMTableWorkspace, PanelDefinition


class _FakePanel:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self.x = 0
        self.y = 0

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height

    def _set_size(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def place_configure(self, *, x: int, y: int) -> None:
        self.x = x
        self.y = y


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
