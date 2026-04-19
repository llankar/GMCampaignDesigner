"""Workspace layout behavior tests for the GM Table."""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from modules.scenarios.gm_table.workspace import (
    PANEL_GUTTER,
    PANEL_MARGIN,
    PANEL_SNAP_THRESHOLD,
    GMTablePanel,
    GMTableWorkspace,
    PanelDefinition,
    SNAP_MODE_LABELS,
    _resize_geometry,
    _resolve_snap_mode,
    _snap_geometry,
)


class _FakePanel:
    def __init__(self, width: int, height: int, *, x: int = 0, y: int = 0) -> None:
        self._width = width
        self._height = height
        self.x = x
        self.y = y
        self.world_x = float(x)
        self.world_y = float(y)
        self.definition = SimpleNamespace(state={})
        self._layout_mode = "floating"
        self._restore_geometry = None
        self._minimized_restore_mode = "floating"
        self.focused = False
        self.lifted = False
        self._project_floating_geometry = None

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

    def floating_geometry_snapshot(self) -> dict[str, float | int]:
        return {
            "x": self.world_x,
            "y": self.world_y,
            "width": self._width,
            "height": self._height,
        }

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

    def apply_floating_geometry(self, geometry: dict[str, float | int], *, screen_geometry=None) -> None:
        self.world_x = float(geometry["x"])
        self.world_y = float(geometry["y"])
        if screen_geometry is None and callable(self._project_floating_geometry):
            screen_geometry = self._project_floating_geometry(geometry)
        visible = screen_geometry or {
            "x": int(round(float(geometry["x"]))),
            "y": int(round(float(geometry["y"]))),
            "width": int(geometry["width"]),
            "height": int(geometry["height"]),
        }
        self.apply_geometry(visible)

    def enter_layout_mode(self, mode: str, geometry: dict[str, int]) -> None:
        if mode != "floating" and self._layout_mode == "floating":
            self._restore_geometry = self.floating_geometry_snapshot()
        self._layout_mode = mode
        self.apply_geometry(geometry)

    def restore_layout(self, **_kwargs) -> bool:
        if self._restore_geometry is None:
            return False
        self._layout_mode = "floating"
        self.apply_floating_geometry(self._restore_geometry)
        return True

    def clear_layout_mode(self) -> None:
        self._layout_mode = "floating"

    def _refresh_window_controls(self) -> None:
        pass

    def minimize(self) -> None:
        self._restore_geometry = self.floating_geometry_snapshot()
        self._minimized_restore_mode = self._layout_mode
        self._layout_mode = "minimized"

    def restore_from_minimized(self, **_kwargs) -> bool:
        if self._layout_mode != "minimized":
            return False
        self._layout_mode = self._minimized_restore_mode or "floating"
        return True

    def serialize_layout_state(self) -> dict[str, object]:
        payload: dict[str, object] = {"layout_mode": self._layout_mode}
        if self._restore_geometry is not None:
            payload["restore_geometry"] = {
                "world_x": self._restore_geometry["x"],
                "world_y": self._restore_geometry["y"],
                "width": self._restore_geometry["width"],
                "height": self._restore_geometry["height"],
            }
        if self._layout_mode == "minimized":
            payload["minimized_restore_mode"] = self._minimized_restore_mode
        return payload

    def set_focus_state(self, focused: bool) -> None:
        self.focused = focused

    def lift(self) -> None:
        self.lifted = True


def _prepare_workspace(workspace, *, width: int = 1400, height: int = 900, camera_x: float = 0.0, camera_y: float = 0.0, zoom: float = 1.0) -> None:
    workspace.surface = SimpleNamespace(winfo_width=lambda: width, winfo_height=lambda: height)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None
    workspace._camera_x = camera_x
    workspace._camera_y = camera_y
    workspace._camera_zoom = zoom
    workspace._home_camera = {"x": camera_x, "y": camera_y, "zoom": zoom}
    workspace._bookmarks = []
    for panel in getattr(workspace, "_panels", {}).values():
        panel._project_floating_geometry = workspace._project_floating_geometry


class _FakePreview:
    def __init__(self) -> None:
        self.width = None
        self.height = None
        self.place_calls: list[dict[str, int]] = []
        self.lifted = False
        self.hidden = False

    def configure(self, **kwargs) -> None:
        if "width" in kwargs:
            self.width = kwargs["width"]
        if "height" in kwargs:
            self.height = kwargs["height"]

    def place(self, **kwargs) -> None:
        if "width" in kwargs or "height" in kwargs:
            raise AssertionError("preview.place() should not receive width/height")
        self.place_calls.append(kwargs)

    def lift(self) -> None:
        self.lifted = True

    def place_forget(self) -> None:
        self.hidden = True


class _FakeWidgetNode:
    def __init__(self, master=None) -> None:
        self.master = master
        self.focused = False
        self.bind_calls: list[tuple[str, object, str | None]] = []
        self.configure_calls: list[dict[str, object]] = []

    def focus_set(self) -> None:
        self.focused = True

    def bind(self, sequence: str, handler, add: str | None = None) -> str:
        self.bind_calls.append((sequence, handler, add))
        return f"bind-{len(self.bind_calls)}"

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(kwargs)


class _FakeBindingTarget:
    def __init__(self) -> None:
        self.bind_calls: list[tuple[str, object, str | None, str]] = []
        self.unbind_calls: list[tuple[str, str | None]] = []

    def bind(self, sequence: str, handler, add: str | None = None) -> str:
        binding_id = f"bind-{len(self.bind_calls) + 1}"
        self.bind_calls.append((sequence, handler, add, binding_id))
        return binding_id

    def unbind(self, sequence: str, binding_id: str | None = None) -> None:
        self.unbind_calls.append((sequence, binding_id))


class _FakeLabel:
    def __init__(self) -> None:
        self.text = None

    def configure(self, **kwargs) -> None:
        if "text" in kwargs:
            self.text = kwargs["text"]


class _FakeCanvas:
    def __init__(self, *, width: int = 156, height: int = 84, measured_width: int = 1, measured_height: int = 1) -> None:
        self._width = width
        self._height = height
        self._measured_width = measured_width
        self._measured_height = measured_height
        self.deleted = False
        self.rectangles: list[tuple[float, float, float, float]] = []

    def winfo_width(self) -> int:
        return self._measured_width

    def winfo_height(self) -> int:
        return self._measured_height

    def cget(self, option: str) -> int:
        if option == "width":
            return self._width
        if option == "height":
            return self._height
        raise KeyError(option)

    def delete(self, _tag: str) -> None:
        self.deleted = True

    def create_rectangle(self, x0: float, y0: float, x1: float, y1: float, **_kwargs) -> None:
        self.rectangles.append((x0, y0, x1, y1))


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


def test_resolve_snap_mode_supports_stacks_quadrants_and_strips() -> None:
    """Dragging near the workspace hotspots should resolve the richer snap targets."""
    surface_w = 1400
    surface_h = 900

    assert _resolve_snap_mode(24, 24, surface_w=surface_w, surface_h=surface_h) == "top_left"
    assert _resolve_snap_mode(surface_w // 2, PANEL_SNAP_THRESHOLD // 2, surface_w=surface_w, surface_h=surface_h) == "maximize"
    assert _resolve_snap_mode(surface_w // 3, PANEL_SNAP_THRESHOLD // 2, surface_w=surface_w, surface_h=surface_h) == "top"
    assert _resolve_snap_mode(PANEL_SNAP_THRESHOLD // 2, surface_h // 2, surface_w=surface_w, surface_h=surface_h) == "left"
    assert _resolve_snap_mode(surface_w // 2, int(surface_h * 0.20), surface_w=surface_w, surface_h=surface_h) == "top_strip"
    assert _resolve_snap_mode(surface_w // 2, int(surface_h * 0.80), surface_w=surface_w, surface_h=surface_h) == "bottom_strip"
    assert _resolve_snap_mode(surface_w - 24, surface_h - 24, surface_w=surface_w, surface_h=surface_h) == "bottom_right"


def test_snap_geometry_supports_quadrants_and_strips() -> None:
    """The richer snap layouts should resolve to stable workspace geometry."""
    surface_w = 1400
    surface_h = 900
    expected_half_width = (surface_w - (PANEL_MARGIN * 2) - PANEL_GUTTER) // 2
    expected_half_height = (surface_h - (PANEL_MARGIN * 2) - PANEL_GUTTER) // 2

    quadrant = _snap_geometry(
        "top_right",
        surface_w=surface_w,
        surface_h=surface_h,
        min_width=GMTablePanel.MIN_WIDTH,
        min_height=GMTablePanel.MIN_HEIGHT,
    )
    strip = _snap_geometry(
        "bottom_strip",
        surface_w=surface_w,
        surface_h=surface_h,
        min_width=GMTablePanel.MIN_WIDTH,
        min_height=GMTablePanel.MIN_HEIGHT,
    )

    assert quadrant == {
        "x": surface_w - PANEL_MARGIN - expected_half_width,
        "y": PANEL_MARGIN,
        "width": expected_half_width,
        "height": expected_half_height,
    }
    assert strip["x"] == PANEL_MARGIN
    assert strip["width"] == surface_w - (PANEL_MARGIN * 2)
    assert strip["y"] > PANEL_MARGIN
    assert GMTablePanel.MIN_HEIGHT <= strip["height"] < (surface_h - (PANEL_MARGIN * 2))


def test_snap_panel_stacks_two_panels_top_and_bottom() -> None:
    """Snapping a panel to the top should pair the next visible panel on the bottom half."""
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

    GMTableWorkspace.snap_panel(workspace, "notes", "top")

    notes = workspace._panels["notes"]
    world_map = workspace._panels["map"]

    assert notes.layout_mode == "top"
    assert world_map.layout_mode == "bottom"
    assert notes.y == PANEL_MARGIN
    assert world_map.y > notes.y
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


def test_resize_to_uses_drag_origin_snapshot_without_cumulative_drift() -> None:
    """Successive drag frames should stay anchored to the initial resize snapshot."""
    panel = GMTablePanel.__new__(GMTablePanel)
    panel._resize_origin = (
        100,
        200,
        {"x": 24.0, "y": 36.0, "width": 400, "height": 300},
        "se",
    )
    panel._get_camera_zoom = lambda: 1.0

    current_geometry = {"x": 24.0, "y": 36.0, "width": 400, "height": 300}
    applied_geometries: list[dict[str, float | int]] = []

    def _floating_geometry_snapshot():
        return dict(current_geometry)

    def _apply_floating_geometry(geometry):
        current_geometry.update(geometry)
        applied_geometries.append(dict(geometry))

    panel.floating_geometry_snapshot = _floating_geometry_snapshot
    panel.apply_floating_geometry = _apply_floating_geometry

    panel._resize_to(SimpleNamespace(x_root=130, y_root=240))
    panel._resize_to(SimpleNamespace(x_root=140, y_root=260))

    assert applied_geometries[0]["width"] == 430
    assert applied_geometries[0]["height"] == 340
    assert applied_geometries[1]["width"] == 440
    assert applied_geometries[1]["height"] == 360
    assert applied_geometries[1]["x"] == 24.0
    assert applied_geometries[1]["y"] == 36.0


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


def test_clamp_panels_reflows_top_strip_panel_when_surface_changes() -> None:
    """Strip layouts should recompute their geometry when the workspace is resized."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    panel = _FakePanel(520, 360, x=84, y=56)
    panel.enter_layout_mode("top_strip", {"x": 12, "y": 12, "width": 1376, "height": 245})
    workspace._panels = {"notes": panel}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._z_order = ["notes"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1180, winfo_height=lambda: 760)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None

    GMTableWorkspace.clamp_panels(workspace)

    assert panel.layout_mode == "top_strip"
    assert panel.x == PANEL_MARGIN
    assert panel.y == PANEL_MARGIN
    assert panel.winfo_width() == 1180 - (PANEL_MARGIN * 2)
    assert panel.winfo_height() == max(
        GMTablePanel.MIN_HEIGHT,
        round((760 - (PANEL_MARGIN * 2)) * 0.28),
    )


def test_preview_snap_target_resizes_preview_without_passing_size_to_place() -> None:
    """Snap preview should resize via widget config so CTk place() does not crash."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    preview = _FakePreview()
    label = _FakeLabel()
    panel = _FakePanel(520, 360, x=84, y=56)
    workspace._panels = {"notes": panel}
    _prepare_workspace(workspace, camera_x=320, camera_y=180)
    workspace._snap_preview = preview
    workspace._snap_preview_label = label
    workspace._snap_preview_mode = None

    GMTableWorkspace.preview_snap_target(workspace, "notes", "left")

    expected_left = _snap_geometry(
        "left",
        surface_w=1400,
        surface_h=900,
        min_width=GMTablePanel.MIN_WIDTH,
        min_height=GMTablePanel.MIN_HEIGHT,
    )
    assert preview.width == expected_left["width"]
    assert preview.height == expected_left["height"]
    assert preview.place_calls[-1] == {"x": expected_left["x"], "y": expected_left["y"]}
    assert label.text == SNAP_MODE_LABELS["left"]
    assert preview.lifted is True
    assert panel.lifted is True
    assert workspace._snap_preview_mode == "left"

    GMTableWorkspace.preview_snap_target(workspace, "notes", "bottom_right")

    expected_quadrant = _snap_geometry(
        "bottom_right",
        surface_w=1400,
        surface_h=900,
        min_width=GMTablePanel.MIN_WIDTH,
        min_height=GMTablePanel.MIN_HEIGHT,
    )
    assert preview.width == expected_quadrant["width"]
    assert preview.height == expected_quadrant["height"]
    assert preview.place_calls[-1] == {"x": expected_quadrant["x"], "y": expected_quadrant["y"]}
    assert label.text == SNAP_MODE_LABELS["bottom_right"]
    assert workspace._snap_preview_mode == "bottom_right"


def test_minimize_and_restore_panel_round_trip() -> None:
    """Workspace minimize/restore should preserve panel state and focus."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {"notes": _FakePanel(520, 360, x=84, y=56)}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._panel_payloads = {}
    workspace._z_order = ["notes"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1400, winfo_height=lambda: 900)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None
    workspace._apply_focus_state = lambda _panel_id: None
    workspace._last_visible_panel_id = lambda **_kwargs: None
    workspace.get_active_panel_id = lambda **_kwargs: "notes"

    GMTableWorkspace.minimize_panel(workspace, "notes")
    assert workspace._panels["notes"].layout_mode == "minimized"

    GMTableWorkspace.restore_panel(workspace, "notes", focus=False)
    assert workspace._panels["notes"].layout_mode == "floating"


def test_bring_to_front_does_not_write_z_into_definition_state() -> None:
    """Focus changes should reorder panels without mutating payload state."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {
        "notes": _FakePanel(520, 360, x=84, y=56),
        "map": _FakePanel(860, 620, x=120, y=72),
    }
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={"text": "plan"}),
        "map": PanelDefinition(panel_id="map", kind="world_map", title="Map", state={"map_name": "Docks"}),
    }
    workspace._z_order = ["notes", "map"]
    workspace._schedule_layout_changed = lambda: None
    workspace._apply_focus_state = lambda _panel_id: None

    GMTableWorkspace.bring_to_front(workspace, "notes")

    assert workspace._z_order == ["map", "notes"]
    assert workspace._definitions["notes"].state == {"text": "plan"}


def test_serialize_persists_minimized_layout_metadata() -> None:
    """Workspace snapshots should retain minimized layout state."""
    panel = _FakePanel(520, 360, x=84, y=56)
    panel.minimize()
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {"notes": panel}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._panel_payloads = {"notes": SimpleNamespace()}
    workspace._z_order = ["notes"]

    snapshot = GMTableWorkspace.serialize(workspace)

    assert snapshot["panels"][0]["state"]["layout_mode"] == "minimized"
    assert snapshot["panels"][0]["state"]["minimized_restore_mode"] == "floating"
    assert snapshot["panels"][0]["state"]["world_x"] == 84.0
    assert snapshot["panels"][0]["state"]["world_y"] == 56.0
    assert snapshot["panels"][0]["state"]["restore_geometry"] == {
        "world_x": 84.0,
        "world_y": 56.0,
        "width": 520,
        "height": 360,
    }


def test_restore_strips_window_metadata_from_definition_state() -> None:
    """Restored panel definitions should keep payload state separate from layout metadata."""
    captured = {}
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace.clear = lambda: None
    workspace.clamp_panels = lambda: None

    def _add_panel(definition, *, geometry=None):
        captured["definition"] = definition
        captured["geometry"] = geometry
        return _FakePanel(geometry["width"], geometry["height"], x=geometry["x"], y=geometry["y"])

    workspace.add_panel = _add_panel

    GMTableWorkspace.restore(
        workspace,
        {
            "panels": [
                {
                    "panel_id": "notes",
                    "kind": "note",
                    "title": "Notes",
                    "state": {
                        "text": "Session recap",
                        "x": 84,
                        "y": 56,
                        "width": 520,
                        "height": 360,
                        "z": 3,
                        "layout_mode": "floating",
                        "minimized_restore_mode": "left",
                        "restore_geometry": {"x": 12, "y": 12, "width": 480, "height": 320},
                    },
                }
            ]
        },
    )

    assert captured["geometry"] == {"x": 84.0, "y": 56.0, "width": 520, "height": 360}
    assert captured["definition"].state == {"text": "Session recap"}


def test_restore_rehydrates_quadrant_layout_mode() -> None:
    """Restoring a saved workspace should preserve the newer snapped layout modes."""
    captured = {}
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace.clear = lambda: None
    workspace.clamp_panels = lambda: None
    workspace._surface_geometry = lambda: (1400, 900)

    def _add_panel(definition, *, geometry=None):
        panel = _FakePanel(geometry["width"], geometry["height"], x=geometry["x"], y=geometry["y"])
        captured["panel"] = panel
        return panel

    workspace.add_panel = _add_panel

    GMTableWorkspace.restore(
        workspace,
        {
            "panels": [
                {
                    "panel_id": "notes",
                    "kind": "note",
                    "title": "Notes",
                    "state": {
                        "x": 84,
                        "y": 56,
                        "width": 520,
                        "height": 360,
                        "layout_mode": "bottom_right",
                        "restore_geometry": {"x": 84, "y": 56, "width": 520, "height": 360},
                    },
                }
            ]
        },
    )

    panel = captured["panel"]
    expected_half_width = (1400 - (PANEL_MARGIN * 2) - PANEL_GUTTER) // 2
    expected_half_height = (900 - (PANEL_MARGIN * 2) - PANEL_GUTTER) // 2

    assert panel.layout_mode == "bottom_right"
    assert panel.x == 1400 - PANEL_MARGIN - expected_half_width
    assert panel.y == 900 - PANEL_MARGIN - expected_half_height
    assert panel.winfo_width() == expected_half_width
    assert panel.winfo_height() == expected_half_height


def test_restore_panel_round_trips_from_quadrant_layout() -> None:
    """Restoring a snapped quadrant panel should return to its prior floating geometry."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {"notes": _FakePanel(520, 360, x=84, y=56)}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._z_order = ["notes"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1400, winfo_height=lambda: 900)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None
    workspace._apply_focus_state = lambda _panel_id: None

    GMTableWorkspace.snap_panel(workspace, "notes", "top_left")
    panel = workspace._panels["notes"]

    assert panel.layout_mode == "top_left"

    GMTableWorkspace.restore_panel(workspace, "notes", focus=False)

    assert panel.layout_mode == "floating"
    assert panel.x == 84
    assert panel.y == 56
    assert panel.winfo_width() == 520
    assert panel.winfo_height() == 360


def test_camera_pan_reprojects_floating_panel_without_changing_size() -> None:
    """Panning the infinite desk should move floating panels while keeping them readable."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    panel = _FakePanel(520, 360, x=240, y=180)
    workspace._panels = {"notes": panel}
    _prepare_workspace(workspace)

    GMTableWorkspace._set_camera(workspace, x=120, y=60)

    assert panel.world_x == 240.0
    assert panel.world_y == 180.0
    assert panel.x == 120
    assert panel.y == 120
    assert panel.winfo_width() == 520
    assert panel.winfo_height() == 360


def test_middle_button_pan_accepts_nested_panel_content_and_ignores_unrelated_widgets() -> None:
    """Middle-drag should pan from any widget inside the surface subtree, but nowhere else."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    surface = _FakeWidgetNode()
    nested_widget = _FakeWidgetNode(master=_FakeWidgetNode(master=_FakeWidgetNode(master=surface)))
    unrelated_widget = _FakeWidgetNode()
    workspace.surface = surface
    workspace._empty_state = _FakeWidgetNode(master=surface)
    workspace._camera_x = 160.0
    workspace._camera_y = 90.0
    workspace._camera_zoom = 1.0
    workspace._pan_origin = None
    workspace._panels = {}
    workspace.clear_snap_preview = lambda: None
    workspace.clamp_panels = lambda: None

    GMTableWorkspace._start_surface_pan(
        workspace,
        SimpleNamespace(widget=nested_widget, num=2, x_root=500, y_root=320),
    )
    GMTableWorkspace._pan_surface_to(workspace, SimpleNamespace(x_root=560, y_root=380))

    assert surface.focused is True
    assert workspace._camera_x == 100.0
    assert workspace._camera_y == 30.0

    GMTableWorkspace._stop_surface_pan(workspace)
    assert workspace._pan_origin is None

    GMTableWorkspace._start_surface_pan(
        workspace,
        SimpleNamespace(widget=unrelated_widget, num=2, x_root=40, y_root=40),
    )

    assert workspace._pan_origin is None


def test_left_drag_pan_remains_limited_to_empty_surface_widgets() -> None:
    """Left-drag panning should stay scoped to the bare table surface and empty state."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    surface = _FakeWidgetNode()
    empty_state = _FakeWidgetNode(master=surface)
    nested_widget = _FakeWidgetNode(master=_FakeWidgetNode(master=surface))
    workspace.surface = surface
    workspace._empty_state = empty_state
    workspace._camera_x = 40.0
    workspace._camera_y = 24.0
    workspace._camera_zoom = 1.0
    workspace._pan_origin = None

    GMTableWorkspace._start_surface_pan(
        workspace,
        SimpleNamespace(widget=nested_widget, num=1, x_root=120, y_root=160),
    )
    assert workspace._pan_origin is None

    GMTableWorkspace._start_surface_pan(
        workspace,
        SimpleNamespace(widget=empty_state, num=1, x_root=120, y_root=160),
    )

    assert workspace._pan_origin == (120, 160, 40.0, 24.0)


def test_bind_surface_navigation_registers_middle_pan_on_workspace_toplevel() -> None:
    """Middle-button pan should be scoped to this workspace via the containing toplevel."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    surface = _FakeWidgetNode()
    empty_state = _FakeWidgetNode(master=surface)
    toplevel = _FakeBindingTarget()
    workspace.surface = surface
    workspace._empty_state = empty_state
    workspace._surface_pan_binding_target = None
    workspace._surface_pan_binding_ids = {}
    workspace.winfo_toplevel = lambda: toplevel

    GMTableWorkspace._bind_surface_navigation(workspace)

    assert {sequence for sequence, *_rest in surface.bind_calls} == {
        "<ButtonPress-1>",
        "<B1-Motion>",
        "<ButtonRelease-1>",
        "<Control-MouseWheel>",
        "<Button-1>",
        "<Home>",
    }
    assert {sequence for sequence, *_rest in empty_state.bind_calls} == {
        "<ButtonPress-1>",
        "<B1-Motion>",
        "<ButtonRelease-1>",
        "<Control-MouseWheel>",
        "<Button-1>",
        "<Home>",
    }
    assert {sequence for sequence, *_rest in toplevel.bind_calls} == {
        "<ButtonPress-2>",
        "<B2-Motion>",
        "<ButtonRelease-2>",
    }

    GMTableWorkspace._handle_workspace_destroy(workspace, SimpleNamespace(widget=workspace))

    assert {sequence for sequence, _binding_id in toplevel.unbind_calls} == {
        "<ButtonPress-2>",
        "<B2-Motion>",
        "<ButtonRelease-2>",
    }


def test_zoom_changes_projection_but_keeps_widget_size_constant() -> None:
    """Navigation zoom should compress spacing, not scale panel chrome."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    panel = _FakePanel(520, 360, x=240, y=180)
    workspace._panels = {"notes": panel}
    _prepare_workspace(workspace)

    GMTableWorkspace._set_camera(workspace, zoom=0.5)

    assert panel.x == 120
    assert panel.y == 90
    assert panel.winfo_width() == 520
    assert panel.winfo_height() == 360


def test_snap_layouts_remain_viewport_relative_with_camera_offset() -> None:
    """Snapped windows should ignore world-camera offset and still use viewport edges."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {
        "notes": _FakePanel(520, 360, x=440, y=312),
        "map": _FakePanel(860, 620, x=820, y=340),
    }
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
        "map": PanelDefinition(panel_id="map", kind="world_map", title="Map", state={}),
    }
    workspace._z_order = ["map", "notes"]
    _prepare_workspace(workspace, camera_x=400, camera_y=240)

    GMTableWorkspace.snap_panel(workspace, "notes", "left")

    notes = workspace._panels["notes"]
    world_map = workspace._panels["map"]
    assert notes.layout_mode == "left"
    assert world_map.layout_mode == "right"
    assert notes.x == PANEL_MARGIN
    assert world_map.x == 1400 - PANEL_MARGIN - world_map.winfo_width()


def test_restore_after_snap_recovers_prior_world_geometry_when_camera_is_offset() -> None:
    """Restoring a snapped panel should return to the stored world coordinates."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    panel = _FakePanel(520, 360, x=48, y=36)
    panel.world_x = 248.0
    panel.world_y = 136.0
    workspace._panels = {"notes": panel}
    workspace._definitions = {
        "notes": PanelDefinition(panel_id="notes", kind="note", title="Notes", state={}),
    }
    workspace._z_order = ["notes"]
    _prepare_workspace(workspace, camera_x=200, camera_y=100)
    workspace._apply_focus_state = lambda _panel_id: None

    GMTableWorkspace.snap_panel(workspace, "notes", "maximize")
    GMTableWorkspace.restore_panel(workspace, "notes", focus=False)

    assert panel.layout_mode == "floating"
    assert panel.world_x == 248.0
    assert panel.world_y == 136.0
    assert panel.x == 48
    assert panel.y == 36


def test_suggest_position_opens_new_panel_near_camera_center() -> None:
    """New floating panels should open around the current viewport center."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {}
    _prepare_workspace(workspace, camera_x=200, camera_y=100, zoom=1.0)

    geometry = GMTableWorkspace._suggest_position(workspace, width=520, height=360)

    assert geometry["x"] == 640.0
    assert geometry["y"] == 370.0
    assert geometry["width"] == 520
    assert geometry["height"] == 360


def test_minimap_click_recenters_camera() -> None:
    """Clicking the minimap should recenter the viewport on the chosen world point."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {}
    _prepare_workspace(workspace)
    workspace._minimap_projection = {"min_x": 100.0, "min_y": 50.0, "scale": 2.0, "padding": 10.0}

    GMTableWorkspace._on_minimap_click(workspace, SimpleNamespace(x=210, y=110))

    assert workspace._camera_x == -500.0
    assert workspace._camera_y == -350.0


def test_serialize_and_restore_round_trip_bookmarks_and_home_camera() -> None:
    """Camera state, home, and bookmarks should persist with the workspace layout."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {}
    workspace._definitions = {}
    workspace._panel_payloads = {}
    workspace._z_order = []
    _prepare_workspace(workspace, camera_x=120, camera_y=80, zoom=0.85)
    workspace._home_camera = {"x": -60.0, "y": -40.0, "zoom": 1.0}
    workspace._bookmarks = [
        {"name": "North Wing", "x": 320.0, "y": 180.0, "zoom": 0.9},
        {"name": "War Room", "x": 900.0, "y": 420.0, "zoom": 1.1},
    ]

    snapshot = GMTableWorkspace.serialize(workspace)

    restored = GMTableWorkspace.__new__(GMTableWorkspace)
    restored.clear = lambda: None
    restored.clamp_panels = lambda: None
    restored.add_panel = lambda definition, *, geometry=None: _FakePanel(geometry["width"], geometry["height"], x=int(geometry["x"]), y=int(geometry["y"]))

    GMTableWorkspace.restore(restored, snapshot)

    assert restored._camera_x == 120.0
    assert restored._camera_y == 80.0
    assert restored._camera_zoom == 0.85
    assert restored._home_camera == {"x": -60.0, "y": -40.0, "zoom": 1.0}
    assert restored.list_bookmarks() == [
        {"name": "North Wing", "x": 320.0, "y": 180.0, "zoom": 0.9},
        {"name": "War Room", "x": 900.0, "y": 420.0, "zoom": 1.1},
    ]


def test_restore_defaults_home_camera_to_saved_camera_when_missing() -> None:
    """Legacy layouts with camera but no home camera should reuse the saved camera."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace.clear = lambda: None
    workspace.clamp_panels = lambda: None
    workspace.add_panel = lambda definition, *, geometry=None: _FakePanel(
        geometry["width"],
        geometry["height"],
        x=int(geometry["x"]),
        y=int(geometry["y"]),
    )

    GMTableWorkspace.restore(
        workspace,
        {
            "camera": {"x": 320.0, "y": 180.0, "zoom": 0.85},
            "panels": [],
        },
    )

    assert workspace._camera_x == 320.0
    assert workspace._camera_y == 180.0
    assert workspace._camera_zoom == 0.85
    assert workspace._home_camera == {"x": 320.0, "y": 180.0, "zoom": 0.85}


def test_restore_ignores_non_dict_layout_payload() -> None:
    """Restore should safely treat missing layout payloads as an empty workspace."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace.clear = lambda: None
    workspace.clamp_panels = lambda: None
    workspace.add_panel = lambda definition, *, geometry=None: _FakePanel(
        geometry["width"],
        geometry["height"],
        x=int(geometry["x"]),
        y=int(geometry["y"]),
    )

    GMTableWorkspace.restore(workspace, None)

    assert workspace._camera_x == 0.0
    assert workspace._camera_y == 0.0
    assert workspace._camera_zoom == 1.0
    assert workspace._home_camera == {"x": 0.0, "y": 0.0, "zoom": 1.0}
    assert workspace.list_bookmarks() == []


def test_refresh_minimap_falls_back_to_configured_canvas_size_before_layout() -> None:
    """The minimap should use configured dimensions when Tk still reports a 1x1 canvas."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {}
    workspace._minimap_canvas = _FakeCanvas()
    workspace._minimap_projection = None
    _prepare_workspace(workspace)

    GMTableWorkspace._refresh_minimap(workspace)

    assert workspace._minimap_canvas.deleted is True
    assert len(workspace._minimap_canvas.rectangles) == 1
    assert workspace._minimap_projection == {
        "min_x": 0.0,
        "min_y": 0.0,
        "scale": (84 - 20) / 900,
        "padding": 10.0,
    }


def test_cascade_panels_offsets_visible_windows() -> None:
    """Cascade should offset visible windows diagonally."""
    workspace = GMTableWorkspace.__new__(GMTableWorkspace)
    workspace._panels = {
        "a": _FakePanel(520, 360, x=24, y=24),
        "b": _FakePanel(520, 360, x=48, y=48),
    }
    workspace._definitions = {
        "a": PanelDefinition(panel_id="a", kind="note", title="A", state={}),
        "b": PanelDefinition(panel_id="b", kind="note", title="B", state={}),
    }
    workspace._panel_payloads = {}
    workspace._z_order = ["a", "b"]
    workspace.surface = SimpleNamespace(winfo_width=lambda: 1400, winfo_height=lambda: 900)
    workspace.update_idletasks = lambda: None
    workspace._schedule_layout_changed = lambda: None
    workspace._apply_focus_state = lambda _panel_id: None

    GMTableWorkspace.cascade_panels(workspace)

    assert workspace._panels["b"].x > workspace._panels["a"].x
    assert workspace._panels["b"].y > workspace._panels["a"].y


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
