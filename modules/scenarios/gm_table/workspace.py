"""Floating workspace primitives for the GM Table."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog
from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk


TABLE_PALETTE = {
    "table_bg": "#11141E",
    "table_alt": "#171C29",
    "table_line": "#2D364B",
    "table_chip": "#20283A",
    "panel_bg": "#0F1523",
    "panel_alt": "#171F30",
    "panel_border": "#34405A",
    "panel_focus": "#7DD3FC",
    "text": "#F4F7FB",
    "muted": "#9EABC2",
    "accent": "#F59E0B",
    "accent_soft": "#453116",
    "danger": "#F87171",
}


DEFAULT_PANEL_SIZES = {
    "campaign_dashboard": (780, 560),
    "world_map": (860, 620),
    "map_tool": (900, 640),
    "scene_flow": (860, 600),
    "image_library": (860, 580),
    "handouts": (760, 560),
    "loot_generator": (620, 520),
    "whiteboard": (900, 640),
    "random_tables": (680, 560),
    "plot_twists": (460, 320),
    "entity": (580, 520),
    "puzzle_display": (700, 540),
    "character_graph": (860, 620),
    "scenario_graph": (860, 620),
    "note": (520, 360),
}

PANEL_MARGIN = 12
PANEL_GUTTER = 12
PANEL_SNAP_THRESHOLD = 48
PANEL_RESIZE_HITBOX = 10
CAMERA_MIN_ZOOM = 0.5
CAMERA_MAX_ZOOM = 1.75
CAMERA_ZOOM_STEP = 0.15
MINIMAP_WIDTH = 176
MINIMAP_HEIGHT = 118
MINIMAP_PADDING = 16
SNAP_LAYOUT_MODES = {
    "left",
    "right",
    "top",
    "bottom",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "top_strip",
    "bottom_strip",
    "maximize",
}
VISIBLE_LAYOUT_MODES = {"floating", *SNAP_LAYOUT_MODES}
SNAP_MODE_LABELS = {
    "left": "Left Column",
    "right": "Right Column",
    "top": "Top Stack",
    "bottom": "Bottom Stack",
    "top_left": "Top Left Quadrant",
    "top_right": "Top Right Quadrant",
    "bottom_left": "Bottom Left Quadrant",
    "bottom_right": "Bottom Right Quadrant",
    "top_strip": "Top Strip",
    "bottom_strip": "Bottom Strip",
    "maximize": "Full Table",
}
SNAP_MENU_LAYOUTS = (
    ("Left Column", "left"),
    ("Right Column", "right"),
    ("Top Stack", "top"),
    ("Bottom Stack", "bottom"),
    ("Top Left Quadrant", "top_left"),
    ("Top Right Quadrant", "top_right"),
    ("Bottom Left Quadrant", "bottom_left"),
    ("Bottom Right Quadrant", "bottom_right"),
    ("Top Strip", "top_strip"),
    ("Bottom Strip", "bottom_strip"),
    ("Full Table", "maximize"),
)
SNAP_COMPLEMENT_MODES = {
    "left": "right",
    "right": "left",
    "top": "bottom",
    "bottom": "top",
}
WORKSPACE_STATE_KEYS = {
    "height",
    "layout_mode",
    "minimized_restore_mode",
    "restore_geometry",
    "width",
    "world_x",
    "world_y",
    "x",
    "y",
    "z",
}


def resolve_default_panel_size(kind: str, state: dict | None = None) -> tuple[int, int]:
    """Return the preferred size for a new panel."""
    width, height = DEFAULT_PANEL_SIZES.get(kind, DEFAULT_PANEL_SIZES["entity"])
    panel_state = state or {}
    if kind != "entity":
        return width, height

    entity_type = str(panel_state.get("entity_type") or "").strip()
    if entity_type == "Scenarios":
        return 920, 680
    if entity_type in {"Informations", "Places", "Bases"}:
        return 760, 580
    return 680, 560


def _payload_state(state: dict | None) -> dict:
    """Strip workspace-only metadata from persisted panel state."""
    if not isinstance(state, dict):
        return {}
    return {
        key: value
        for key, value in state.items()
        if key not in WORKSPACE_STATE_KEYS
    }


def _clamp(value: int, minimum: int, maximum: int) -> int:
    """Clamp a value."""
    return max(minimum, min(maximum, value))


def _coerce_float(value, default: float = 0.0) -> float:
    """Return a float with a safe fallback."""
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize_camera(camera: dict | None = None) -> dict[str, float]:
    """Return a safe camera snapshot."""
    snapshot = camera or {}
    return {
        "x": round(_coerce_float(snapshot.get("x", 0.0)), 2),
        "y": round(_coerce_float(snapshot.get("y", 0.0)), 2),
        "zoom": round(
            max(CAMERA_MIN_ZOOM, min(CAMERA_MAX_ZOOM, _coerce_float(snapshot.get("zoom", 1.0), 1.0))),
            3,
        ),
    }


def _normalize_bookmark(name: str, camera: dict | None = None) -> dict[str, object]:
    """Return a serializable bookmark payload."""
    label = str(name or "").strip() or "Bookmark"
    snapshot = _normalize_camera(camera)
    return {
        "name": label,
        "x": snapshot["x"],
        "y": snapshot["y"],
        "zoom": snapshot["zoom"],
    }


def _snap(value: int, grid: int = 24) -> int:
    """Snap a value to the nearest grid slot."""
    if grid <= 1:
        return value
    return int(round(value / grid) * grid)


def _normalize_floating_geometry(
    x: float | int,
    y: float | int,
    width: int,
    height: int,
    *,
    min_width: int,
    min_height: int,
) -> dict[str, float | int]:
    """Normalize a floating panel world geometry without clamping it to the viewport."""
    return {
        "x": round(_coerce_float(x), 2),
        "y": round(_coerce_float(y), 2),
        "width": max(int(min_width), int(width)),
        "height": max(int(min_height), int(height)),
    }


def _world_geometry_from_state(
    state: dict | None,
    *,
    default_x: float = 24.0,
    default_y: float = 24.0,
    default_width: int,
    default_height: int,
    min_width: int,
    min_height: int,
) -> dict[str, float | int]:
    """Resolve a saved floating geometry from world or legacy viewport-local fields."""
    payload = state or {}
    return _normalize_floating_geometry(
        payload.get("world_x", payload.get("x", default_x)),
        payload.get("world_y", payload.get("y", default_y)),
        int(payload.get("width", default_width)),
        int(payload.get("height", default_height)),
        min_width=min_width,
        min_height=min_height,
    )


def _surface_dimensions(surface, *, minimum_width: int = 640, minimum_height: int = 420) -> tuple[int, int]:
    """Return safe surface dimensions."""
    try:
        width = int(surface.winfo_width())
    except Exception:
        width = minimum_width
    try:
        height = int(surface.winfo_height())
    except Exception:
        height = minimum_height
    return max(minimum_width, width), max(minimum_height, height)


def _constrain_panel_geometry(
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    surface_w: int,
    surface_h: int,
    min_width: int,
    min_height: int,
    margin: int = PANEL_MARGIN,
) -> dict[str, int]:
    """Clamp panel geometry so it stays visible inside the workspace."""
    max_width = max(min_width, int(surface_w) - (margin * 2))
    max_height = max(min_height, int(surface_h) - (margin * 2))
    width = _clamp(int(width), int(min_width), max_width)
    height = _clamp(int(height), int(min_height), max_height)
    x = _clamp(int(x), margin, max(margin, int(surface_w) - width - margin))
    y = _clamp(int(y), margin, max(margin, int(surface_h) - height - margin))
    return {"x": x, "y": y, "width": width, "height": height}


def _resolve_snap_mode(
    pointer_x: int,
    pointer_y: int,
    *,
    surface_w: int,
    surface_h: int,
    threshold: int = PANEL_SNAP_THRESHOLD,
) -> str | None:
    """Return the Windows-like snap target under the pointer."""
    width = max(1, int(surface_w))
    height = max(1, int(surface_h))
    x = int(pointer_x)
    y = int(pointer_y)
    if x < 0 or y < 0 or x > width or y > height:
        return None

    x_ratio = x / width
    y_ratio = y / height
    threshold = max(16, int(threshold))

    if y <= threshold:
        if x_ratio <= 0.24:
            return "top_left"
        if x_ratio >= 0.76:
            return "top_right"
        if 0.40 <= x_ratio <= 0.60:
            return "maximize"
        return "top"
    if y >= height - threshold:
        if x_ratio <= 0.24:
            return "bottom_left"
        if x_ratio >= 0.76:
            return "bottom_right"
        return "bottom"
    if x <= threshold:
        if y_ratio <= 0.24:
            return "top_left"
        if y_ratio >= 0.76:
            return "bottom_left"
        return "left"
    if x >= width - threshold:
        if y_ratio <= 0.24:
            return "top_right"
        if y_ratio >= 0.76:
            return "bottom_right"
        return "right"
    if 0.18 <= x_ratio <= 0.82 and 0.14 <= y_ratio <= 0.28:
        return "top_strip"
    if 0.18 <= x_ratio <= 0.82 and 0.72 <= y_ratio <= 0.86:
        return "bottom_strip"
    return None


def _snap_geometry(
    mode: str,
    *,
    surface_w: int,
    surface_h: int,
    min_width: int,
    min_height: int,
    margin: int = PANEL_MARGIN,
    gutter: int = PANEL_GUTTER,
) -> dict[str, int]:
    """Return the target geometry for a snapped or maximized panel."""
    full_width = max(min_width, int(surface_w) - (margin * 2))
    full_height = max(min_height, int(surface_h) - (margin * 2))
    split_width = max(min_width * 2, full_width - gutter)
    split_height = max(min_height * 2, full_height - gutter)
    half_width = max(min_width, split_width // 2)
    half_height = max(min_height, split_height // 2)
    strip_height = _clamp(
        int(round(full_height * 0.28)),
        min_height,
        max(min_height, full_height - min_height - gutter),
    )

    if mode == "maximize":
        return _constrain_panel_geometry(
            margin,
            margin,
            full_width,
            full_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )

    if mode == "left":
        return _constrain_panel_geometry(
            margin,
            margin,
            half_width,
            full_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "right":
        return _constrain_panel_geometry(
            int(surface_w) - margin - half_width,
            margin,
            half_width,
            full_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "top":
        return _constrain_panel_geometry(
            margin,
            margin,
            full_width,
            half_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "bottom":
        return _constrain_panel_geometry(
            margin,
            int(surface_h) - margin - half_height,
            full_width,
            half_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "top_left":
        return _constrain_panel_geometry(
            margin,
            margin,
            half_width,
            half_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "top_right":
        return _constrain_panel_geometry(
            int(surface_w) - margin - half_width,
            margin,
            half_width,
            half_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "bottom_left":
        return _constrain_panel_geometry(
            margin,
            int(surface_h) - margin - half_height,
            half_width,
            half_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "bottom_right":
        return _constrain_panel_geometry(
            int(surface_w) - margin - half_width,
            int(surface_h) - margin - half_height,
            half_width,
            half_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "top_strip":
        return _constrain_panel_geometry(
            margin,
            margin,
            full_width,
            strip_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )
    if mode == "bottom_strip":
        return _constrain_panel_geometry(
            margin,
            int(surface_h) - margin - strip_height,
            full_width,
            strip_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )

    raise ValueError(f"Unsupported snap mode: {mode}")


def _resize_geometry(
    direction: str,
    *,
    start_geometry: dict[str, int],
    delta_x: int,
    delta_y: int,
    surface_w: int,
    surface_h: int,
    min_width: int,
    min_height: int,
    margin: int = PANEL_MARGIN,
) -> dict[str, int]:
    """Return resized panel geometry for an edge or corner drag."""
    left = int(start_geometry.get("x", 0))
    top = int(start_geometry.get("y", 0))
    right = left + int(start_geometry.get("width", min_width))
    bottom = top + int(start_geometry.get("height", min_height))

    if "w" in direction:
        left += int(delta_x)
    if "e" in direction:
        right += int(delta_x)
    if "n" in direction:
        top += int(delta_y)
    if "s" in direction:
        bottom += int(delta_y)

    left = min(left, right - min_width)
    top = min(top, bottom - min_height)
    right = max(right, left + min_width)
    bottom = max(bottom, top + min_height)

    left = _clamp(left, margin, max(margin, int(surface_w) - min_width - margin))
    top = _clamp(top, margin, max(margin, int(surface_h) - min_height - margin))
    right = _clamp(right, left + min_width, max(left + min_width, int(surface_w) - margin))
    bottom = _clamp(bottom, top + min_height, max(top + min_height, int(surface_h) - margin))

    return _constrain_panel_geometry(
        left,
        top,
        right - left,
        bottom - top,
        surface_w=surface_w,
        surface_h=surface_h,
        min_width=min_width,
        min_height=min_height,
        margin=margin,
    )


def _resize_floating_geometry(
    direction: str,
    *,
    start_geometry: dict[str, float | int],
    delta_x: int,
    delta_y: int,
    zoom: float,
    min_width: int,
    min_height: int,
) -> dict[str, float | int]:
    """Return resized floating geometry without constraining it to the viewport."""
    width = int(start_geometry.get("width", min_width))
    height = int(start_geometry.get("height", min_height))
    x = _coerce_float(start_geometry.get("x", 0.0))
    y = _coerce_float(start_geometry.get("y", 0.0))
    zoom = max(CAMERA_MIN_ZOOM, float(zoom))

    if "w" in direction:
        x += delta_x / zoom
        width -= int(delta_x)
    if "e" in direction:
        width += int(delta_x)
    if "n" in direction:
        y += delta_y / zoom
        height -= int(delta_y)
    if "s" in direction:
        height += int(delta_y)

    if width < min_width:
        if "w" in direction:
            x = _coerce_float(start_geometry.get("x", 0.0)) + ((int(start_geometry.get("width", min_width)) - min_width) / zoom)
        width = int(min_width)
    if height < min_height:
        if "n" in direction:
            y = _coerce_float(start_geometry.get("y", 0.0)) + ((int(start_geometry.get("height", min_height)) - min_height) / zoom)
        height = int(min_height)

    return _normalize_floating_geometry(
        x,
        y,
        width,
        height,
        min_width=min_width,
        min_height=min_height,
    )


@dataclass(slots=True)
class PanelDefinition:
    """Serializable GM Table panel description."""

    panel_id: str
    kind: str
    title: str
    state: dict


class GMTablePanel(ctk.CTkFrame):
    """Floating panel with drag, resize, and window controls."""

    MIN_WIDTH = 300
    MIN_HEIGHT = 220

    def __init__(
        self,
        master,
        *,
        definition: PanelDefinition,
        width: int,
        height: int,
        on_focus: Callable[[str], None],
        on_close: Callable[[str], None],
        on_geometry_changed: Callable[[str], None],
        project_floating_geometry: Callable[[dict[str, float | int]], dict[str, int]],
        screen_to_world: Callable[[float, float], tuple[float, float]],
        get_camera_zoom: Callable[[], float],
        on_snap_requested: Callable[[str, str], None],
        on_snap_preview_changed: Callable[[str, str | None], None],
        on_toggle_maximize: Callable[[str], None],
        on_window_action: Callable[[str, str], None],
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=TABLE_PALETTE["panel_bg"],
            corner_radius=22,
            border_width=1,
            border_color=TABLE_PALETTE["panel_border"],
        )
        self.definition = definition
        self._on_focus = on_focus
        self._on_close = on_close
        self._on_geometry_changed = on_geometry_changed
        self._project_floating_geometry = project_floating_geometry
        self._screen_to_world = screen_to_world
        self._get_camera_zoom = get_camera_zoom
        self._on_snap_requested = on_snap_requested
        self._on_snap_preview_changed = on_snap_preview_changed
        self._on_toggle_maximize = on_toggle_maximize
        self._on_window_action = on_window_action
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._resize_origin: tuple[int, int, dict[str, int], str] | None = None
        self._restore_geometry: dict[str, int] | None = None
        self._layout_mode = "floating"
        self._minimized_restore_mode = "floating"
        self._world_geometry = _normalize_floating_geometry(
            0,
            0,
            width,
            height,
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self._current_geometry = {"x": 0, "y": 0, "width": width, "height": height}
        self._resize_handles: dict[str, tk.Frame] = {}
        self._is_focused = False
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self, fg_color=TABLE_PALETTE["panel_alt"], corner_radius=18)
        self.header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self.header.grid_columnconfigure(0, weight=1)

        self.eyebrow_label = ctk.CTkLabel(
            self.header,
            text=(definition.kind or "panel").replace("_", " ").title(),
            text_color=TABLE_PALETTE["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.eyebrow_label.grid(row=0, column=0, padx=(14, 8), pady=(10, 0), sticky="w")

        self.title_label = ctk.CTkLabel(
            self.header,
            text=definition.title,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=17, weight="bold"),
            anchor="w",
        )
        self.title_label.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")

        self.controls = ctk.CTkFrame(self.header, fg_color="transparent")
        self.controls.grid(row=0, column=1, rowspan=2, padx=(8, 10), pady=10, sticky="ne")

        self.minimize_button = ctk.CTkButton(
            self.controls,
            text="-",
            width=30,
            height=28,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=lambda: self._dispatch_window_action("minimize"),
        )
        self.minimize_button.pack(side="left", padx=(0, 6))

        self.maximize_button = ctk.CTkButton(
            self.controls,
            text="Max",
            width=54,
            height=28,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=lambda: self._dispatch_window_action("toggle_maximize"),
        )
        self.maximize_button.pack(side="left", padx=(0, 6))

        self.actions_button = ctk.CTkButton(
            self.controls,
            text="...",
            width=34,
            height=28,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=self._show_actions_menu,
        )
        self.actions_button.pack(side="left", padx=(0, 6))

        self.close_button = ctk.CTkButton(
            self.controls,
            text="x",
            width=30,
            height=28,
            fg_color=TABLE_PALETTE["accent_soft"],
            hover_color="#5B3414",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=lambda: self._on_close(self.definition.panel_id),
        )
        self.close_button.pack(side="left")

        self._actions_menu = tk.Menu(self, tearoff=0)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self.resize_handle = ctk.CTkLabel(
            self,
            text="//",
            width=32,
            height=24,
            fg_color=TABLE_PALETTE["table_chip"],
            text_color=TABLE_PALETTE["muted"],
            corner_radius=10,
        )
        self.resize_handle.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")
        try:
            self.resize_handle.configure(cursor="size_nw_se")
        except Exception:
            pass

        self._bind_focus(self)
        self._bind_focus(self.header)
        self._bind_focus(self.body)
        self._bind_focus(self.title_label)
        self._bind_focus(self.eyebrow_label)
        self._install_drag_bindings()
        self._install_resize_bindings()
        self._refresh_window_controls()

    def _bind_focus(self, widget) -> None:
        """Raise the panel when clicked."""
        for sequence in ("<Button-1>", "<ButtonPress-1>"):
            widget.bind(sequence, lambda _event: self._on_focus(self.definition.panel_id), add="+")

    def _install_drag_bindings(self) -> None:
        """Enable drag interactions from the header."""
        for widget in (self.header, self.title_label, self.eyebrow_label):
            widget.bind("<ButtonPress-1>", self._start_drag, add="+")
            widget.bind("<B1-Motion>", self._drag_to, add="+")
            widget.bind("<ButtonRelease-1>", self._stop_drag, add="+")
            widget.bind("<Double-Button-1>", self._toggle_maximize, add="+")

    def _install_resize_bindings(self) -> None:
        """Enable drag-resize interactions."""
        self._bind_resize_widget(self.resize_handle, "se")
        handle_specs = {
            "n": {"cursor": "sb_v_double_arrow", "x": 18, "y": 0, "relwidth": 1.0, "width": -36, "height": PANEL_RESIZE_HITBOX},
            "s": {"cursor": "sb_v_double_arrow", "x": 18, "rely": 1.0, "y": -PANEL_RESIZE_HITBOX, "relwidth": 1.0, "width": -36, "height": PANEL_RESIZE_HITBOX},
            "w": {"cursor": "sb_h_double_arrow", "x": 0, "y": 18, "width": PANEL_RESIZE_HITBOX, "relheight": 1.0, "height": -36},
            "e": {"cursor": "sb_h_double_arrow", "relx": 1.0, "x": -PANEL_RESIZE_HITBOX, "y": 18, "width": PANEL_RESIZE_HITBOX, "relheight": 1.0, "height": -36},
            "nw": {"cursor": "size_nw_se", "x": 0, "y": 0, "width": PANEL_RESIZE_HITBOX + 4, "height": PANEL_RESIZE_HITBOX + 4},
            "ne": {"cursor": "size_ne_sw", "relx": 1.0, "x": -(PANEL_RESIZE_HITBOX + 4), "y": 0, "width": PANEL_RESIZE_HITBOX + 4, "height": PANEL_RESIZE_HITBOX + 4},
            "sw": {"cursor": "size_ne_sw", "x": 0, "rely": 1.0, "y": -(PANEL_RESIZE_HITBOX + 4), "width": PANEL_RESIZE_HITBOX + 4, "height": PANEL_RESIZE_HITBOX + 4},
            "se": {"cursor": "size_nw_se", "relx": 1.0, "rely": 1.0, "x": -(PANEL_RESIZE_HITBOX + 4), "y": -(PANEL_RESIZE_HITBOX + 4), "width": PANEL_RESIZE_HITBOX + 4, "height": PANEL_RESIZE_HITBOX + 4},
        }
        for direction, spec in handle_specs.items():
            cursor = spec.pop("cursor")
            handle = tk.Frame(
                self,
                bg=TABLE_PALETTE["panel_bg"],
                highlightthickness=0,
                bd=0,
                cursor=cursor,
            )
            handle.place(**spec)
            self._bind_resize_widget(handle, direction)
            self._resize_handles[direction] = handle
        self.resize_handle.lift()

    def _bind_resize_widget(self, widget, direction: str) -> None:
        """Bind a widget as an active resize target."""
        widget.bind("<ButtonPress-1>", lambda event, value=direction: self._start_resize(event, value), add="+")
        widget.bind("<B1-Motion>", self._resize_to, add="+")
        widget.bind("<ButtonRelease-1>", self._stop_resize, add="+")

    @property
    def layout_mode(self) -> str:
        """Return the current layout mode."""
        return self._layout_mode

    def enter_layout_mode(self, mode: str, geometry: dict[str, int]) -> None:
        """Apply a docked or maximized layout and remember the floating geometry."""
        if mode != "floating" and mode != "minimized" and self._layout_mode == "floating":
            self._restore_geometry = self.floating_geometry_snapshot()
        if mode != "minimized":
            self._minimized_restore_mode = mode
        self._layout_mode = mode
        self.apply_geometry(geometry)
        self._refresh_window_controls()

    def restore_layout(self, *, anchor_x_root: int | None = None, anchor_y_root: int | None = None) -> bool:
        """Restore the last floating geometry from a snapped or maximized state."""
        if not self._restore_geometry:
            return False
        geometry = dict(self._restore_geometry)
        if anchor_x_root is not None and anchor_y_root is not None:
            try:
                surface_root_x = int(self.master.winfo_rootx())
                surface_root_y = int(self.master.winfo_rooty())
            except Exception:
                surface_root_x = 0
                surface_root_y = 0
            current_width = max(1, int(self.winfo_width()))
            current_height = max(1, int(self.winfo_height()))
            try:
                pointer_ratio_x = (int(anchor_x_root) - int(self.winfo_rootx())) / current_width
            except Exception:
                pointer_ratio_x = 0.5
            try:
                pointer_ratio_y = (int(anchor_y_root) - int(self.winfo_rooty())) / current_height
            except Exception:
                pointer_ratio_y = 0.15
            pointer_ratio_x = max(0.0, min(1.0, pointer_ratio_x))
            pointer_ratio_y = max(0.0, min(0.35, pointer_ratio_y))
            restore_width = int(geometry.get("width", current_width))
            restore_height = int(geometry.get("height", current_height))
            screen_x = int(round((int(anchor_x_root) - surface_root_x) - (restore_width * pointer_ratio_x)))
            screen_y = int(round((int(anchor_y_root) - surface_root_y) - (restore_height * pointer_ratio_y)))
            world_x, world_y = self._screen_to_world(screen_x, screen_y)
            geometry["x"] = world_x
            geometry["y"] = world_y
        floating_geometry = _normalize_floating_geometry(
            geometry.get("x", self._world_geometry["x"]),
            geometry.get("y", self._world_geometry["y"]),
            int(geometry.get("width", self.winfo_width())),
            int(geometry.get("height", self.winfo_height())),
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self._layout_mode = "floating"
        self._minimized_restore_mode = "floating"
        self.apply_floating_geometry(floating_geometry)
        self._refresh_window_controls()
        return True

    def minimize(self) -> None:
        """Hide the panel and remember how it should restore."""
        if self._layout_mode == "minimized":
            return
        restore_mode = self._layout_mode if self._layout_mode in VISIBLE_LAYOUT_MODES else "floating"
        if restore_mode == "floating":
            self._restore_geometry = self.floating_geometry_snapshot()
        self._minimized_restore_mode = restore_mode
        self._layout_mode = "minimized"
        self.place_forget()
        self._refresh_window_controls()

    def restore_from_minimized(self, *, surface_w: int, surface_h: int) -> bool:
        """Restore a minimized panel to its prior visible state."""
        if self._layout_mode != "minimized":
            return False
        mode = self._minimized_restore_mode or "floating"
        if mode == "floating":
            geometry = dict(self._restore_geometry or self._world_geometry)
            geometry = _normalize_floating_geometry(
                geometry.get("x", 24),
                geometry.get("y", 24),
                int(geometry.get("width", self.MIN_WIDTH)),
                int(geometry.get("height", self.MIN_HEIGHT)),
                min_width=self.MIN_WIDTH,
                min_height=self.MIN_HEIGHT,
            )
            self._layout_mode = "floating"
            self.apply_floating_geometry(geometry)
        else:
            self._layout_mode = mode
            self.apply_geometry(
                _snap_geometry(
                    mode,
                    surface_w=surface_w,
                    surface_h=surface_h,
                    min_width=self.MIN_WIDTH,
                    min_height=self.MIN_HEIGHT,
                )
            )
        self._refresh_window_controls()
        return True

    def clear_layout_mode(self) -> None:
        """Return to freeform mode without changing geometry."""
        self._layout_mode = "floating"
        self._minimized_restore_mode = "floating"
        self._refresh_window_controls()

    def apply_geometry(self, geometry: dict[str, int]) -> None:
        """Apply panel geometry in one place."""
        self._apply_geometry(
            x=int(geometry.get("x", self._current_geometry["x"])),
            y=int(geometry.get("y", self._current_geometry["y"])),
            width=int(geometry.get("width", self._current_geometry["width"])),
            height=int(geometry.get("height", self._current_geometry["height"])),
        )

    def apply_floating_geometry(
        self,
        geometry: dict[str, float | int],
        *,
        screen_geometry: dict[str, int] | None = None,
    ) -> None:
        """Apply a floating world geometry and reproject it into the viewport."""
        self._world_geometry = _normalize_floating_geometry(
            geometry.get("x", self._world_geometry["x"]),
            geometry.get("y", self._world_geometry["y"]),
            int(geometry.get("width", self._world_geometry["width"])),
            int(geometry.get("height", self._world_geometry["height"])),
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        projected = screen_geometry or self._project_floating_geometry(self._world_geometry)
        self._apply_geometry(
            x=int(projected.get("x", self._current_geometry["x"])),
            y=int(projected.get("y", self._current_geometry["y"])),
            width=int(projected.get("width", self._current_geometry["width"])),
            height=int(projected.get("height", self._current_geometry["height"])),
        )

    def serialize_layout_state(self) -> dict[str, object]:
        """Return panel layout metadata for persistence."""
        payload: dict[str, object] = {"layout_mode": self._layout_mode}
        if self._restore_geometry:
            payload["restore_geometry"] = {
                "world_x": self._restore_geometry["x"],
                "world_y": self._restore_geometry["y"],
                "width": self._restore_geometry["width"],
                "height": self._restore_geometry["height"],
            }
        if self._layout_mode == "minimized" or self._minimized_restore_mode != "floating":
            payload["minimized_restore_mode"] = self._minimized_restore_mode
        return payload

    def _dispatch_window_action(self, action: str) -> None:
        """Forward a window action to the workspace."""
        self._on_window_action(self.definition.panel_id, action)

    def _show_actions_menu(self) -> None:
        """Open the window actions menu."""
        self._on_focus(self.definition.panel_id)
        menu = self._actions_menu
        menu.delete(0, "end")
        menu.add_command(label="Restore", command=lambda: self._dispatch_window_action("restore"))
        menu.add_command(label="Minimize", command=lambda: self._dispatch_window_action("minimize"))
        maximize_label = "Restore Size" if self._layout_mode in SNAP_LAYOUT_MODES else "Maximize"
        menu.add_command(label=maximize_label, command=lambda: self._dispatch_window_action("toggle_maximize"))
        menu.add_separator()
        snap_menu = tk.Menu(menu, tearoff=0)
        for label, mode in SNAP_MENU_LAYOUTS:
            snap_menu.add_command(label=label, command=lambda value=mode: self._dispatch_window_action(f"snap:{value}"))
        menu.add_cascade(label="Snap Layout", menu=snap_menu)
        menu.add_separator()
        menu.add_command(label="Close Others", command=lambda: self._dispatch_window_action("close_others"))
        menu.add_command(label="Cascade Windows", command=lambda: self._dispatch_window_action("cascade_all"))
        menu.add_command(label="Tile Windows", command=lambda: self._dispatch_window_action("tile_all"))
        menu.add_command(label="Restore All", command=lambda: self._dispatch_window_action("restore_all"))
        menu.add_separator()
        menu.add_command(label="Close", command=lambda: self._on_close(self.definition.panel_id))

        x = self.actions_button.winfo_rootx()
        y = self.actions_button.winfo_rooty() + self.actions_button.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _refresh_window_controls(self) -> None:
        """Refresh control labels for the current layout mode."""
        maximize_label = "Restore" if self._layout_mode in SNAP_LAYOUT_MODES else "Max"
        self.maximize_button.configure(text=maximize_label)

    def _start_drag(self, event) -> None:
        """Start moving a panel."""
        if self._layout_mode == "minimized":
            return
        self._on_focus(self.definition.panel_id)
        self._on_snap_preview_changed(self.definition.panel_id, None)
        if self._layout_mode != "floating":
            self.restore_layout(anchor_x_root=event.x_root, anchor_y_root=event.y_root)
        geometry = self.floating_geometry_snapshot()
        self._drag_origin = (
            event.x_root,
            event.y_root,
            int(round(float(geometry["x"]) * 100)),
            int(round(float(geometry["y"]) * 100)),
        )

    def _drag_to(self, event) -> None:
        """Move the panel with the pointer."""
        if self._drag_origin is None:
            return
        root_x, root_y, start_x, start_y = self._drag_origin
        zoom = max(CAMERA_MIN_ZOOM, float(self._get_camera_zoom()))
        geometry = self.floating_geometry_snapshot()
        geometry["x"] = (start_x / 100.0) + ((event.x_root - root_x) / zoom)
        geometry["y"] = (start_y / 100.0) + ((event.y_root - root_y) / zoom)
        self.apply_floating_geometry(geometry)
        self._on_snap_preview_changed(self.definition.panel_id, self._resolve_drag_snap_mode(event))

    def _stop_drag(self, event=None) -> None:
        """Stop dragging and snap to the workspace grid."""
        if self._drag_origin is None:
            return
        snap_mode = self._resolve_drag_snap_mode(event) if event is not None else None
        self._on_snap_preview_changed(self.definition.panel_id, None)
        self._drag_origin = None
        if snap_mode is not None:
            self._on_snap_requested(self.definition.panel_id, snap_mode)
            return
        geometry = self.floating_geometry_snapshot()
        geometry = _normalize_floating_geometry(
            _snap(int(round(float(geometry["x"])))),
            _snap(int(round(float(geometry["y"])))),
            _snap(int(geometry["width"])),
            _snap(int(geometry["height"])),
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.clear_layout_mode()
        self.apply_floating_geometry(geometry)
        self._on_geometry_changed(self.definition.panel_id)

    def _toggle_maximize(self, _event=None) -> None:
        """Toggle maximized mode from the header."""
        self._drag_origin = None
        self._on_snap_preview_changed(self.definition.panel_id, None)
        self._on_toggle_maximize(self.definition.panel_id)

    def _start_resize(self, event, direction: str = "se") -> None:
        """Start resizing a panel."""
        if self._layout_mode == "minimized":
            return
        self._on_focus(self.definition.panel_id)
        self._on_snap_preview_changed(self.definition.panel_id, None)
        self.clear_layout_mode()
        self._resize_origin = (event.x_root, event.y_root, self.floating_geometry_snapshot(), direction)

    def _resize_to(self, event) -> None:
        """Resize the panel with the pointer."""
        if self._resize_origin is None:
            return
        root_x, root_y, start_geometry, direction = self._resize_origin
        start_world = self.floating_geometry_snapshot()
        geometry = _resize_floating_geometry(
            direction,
            start_geometry=start_world,
            delta_x=event.x_root - root_x,
            delta_y=event.y_root - root_y,
            zoom=max(CAMERA_MIN_ZOOM, float(self._get_camera_zoom())),
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.apply_floating_geometry(geometry)

    def _stop_resize(self, _event=None) -> None:
        """Finish resizing and snap dimensions."""
        if self._resize_origin is None:
            return
        self._resize_origin = None
        geometry = self.floating_geometry_snapshot()
        geometry = _normalize_floating_geometry(
            _snap(int(round(float(geometry["x"])))),
            _snap(int(round(float(geometry["y"])))),
            _snap(int(geometry["width"])),
            _snap(int(geometry["height"])),
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.apply_floating_geometry(geometry)
        self._on_geometry_changed(self.definition.panel_id)

    def set_focus_state(self, focused: bool) -> None:
        """Update focus styling."""
        self._is_focused = bool(focused)
        self.configure(border_color=TABLE_PALETTE["panel_focus"] if focused else TABLE_PALETTE["panel_border"])

    def set_title(self, title: str) -> None:
        """Refresh the visible title."""
        self.definition.title = title
        self.title_label.configure(text=title)

    def geometry_snapshot(self) -> dict[str, int]:
        """Return the last known panel geometry."""
        return dict(self._current_geometry)

    def floating_geometry_snapshot(self) -> dict[str, float | int]:
        """Return the persisted world geometry for floating restore/state."""
        return dict(self._world_geometry)

    def _apply_geometry(self, *, x: int, y: int, width: int, height: int) -> None:
        """Apply size and position together."""
        self._current_geometry = {
            "x": int(x),
            "y": int(y),
            "width": max(self.MIN_WIDTH, int(width)),
            "height": max(self.MIN_HEIGHT, int(height)),
        }
        self._set_size(self._current_geometry["width"], self._current_geometry["height"])
        self.place_configure(x=self._current_geometry["x"], y=self._current_geometry["y"])

    def _set_size(self, width: int, height: int) -> None:
        """Update the CTk widget size."""
        width = max(self.MIN_WIDTH, int(width))
        height = max(self.MIN_HEIGHT, int(height))
        self.configure(width=width, height=height)
        try:
            self.place_configure(width=width, height=height)
        except Exception:
            pass
        self.resize_handle.lift()

    def _resolve_drag_snap_mode(self, event) -> str | None:
        """Resolve the current drag pointer against the workspace snap map."""
        if event is None:
            return None
        try:
            pointer_x = int(event.x_root) - int(self.master.winfo_rootx())
            pointer_y = int(event.y_root) - int(self.master.winfo_rooty())
            surface_w, surface_h = _surface_dimensions(self.master)
        except Exception:
            return None
        return _resolve_snap_mode(pointer_x, pointer_y, surface_w=surface_w, surface_h=surface_h)


class GMTableWorkspace(ctk.CTkFrame):
    """Manage floating GM Table panels."""

    def __init__(
        self,
        master,
        *,
        on_panel_build: Callable[[ctk.CTkFrame, PanelDefinition], object],
        on_layout_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color=TABLE_PALETTE["table_bg"], corner_radius=28)
        self._build_panel = on_panel_build
        self._layout_changed_callback = on_layout_changed
        self._panels: dict[str, GMTablePanel] = {}
        self._definitions: dict[str, PanelDefinition] = {}
        self._panel_payloads: dict[str, object] = {}
        self._z_order: list[str] = []
        self._save_job: str | None = None
        self._surface_resize_job: str | None = None
        self._disposed = False
        self._snap_preview_mode: str | None = None
        self._camera_x = 0.0
        self._camera_y = 0.0
        self._camera_zoom = 1.0
        self._home_camera = _normalize_camera()
        self._bookmarks: list[dict[str, object]] = []
        self._pan_origin: tuple[int, int, float, float] | None = None
        self._minimap_projection: dict[str, float] | None = None
        self._surface_pan_binding_target = None
        self._surface_pan_binding_ids: dict[str, str] = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.surface = ctk.CTkFrame(
            self,
            fg_color=TABLE_PALETTE["table_bg"],
            corner_radius=24,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        self.surface.grid(row=0, column=0, sticky="nsew", padx=18, pady=(0, 10))
        self.surface.bind("<Configure>", self._on_surface_configure, add="+")

        self._snap_preview = ctk.CTkFrame(
            self.surface,
            fg_color=TABLE_PALETTE["accent_soft"],
            corner_radius=26,
            border_width=2,
            border_color=TABLE_PALETTE["panel_focus"],
        )
        self._snap_preview_label = ctk.CTkLabel(
            self._snap_preview,
            text="",
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._snap_preview_label.place(relx=0.5, rely=0.5, anchor="center")
        self._snap_preview.place_forget()

        self._nav_hud = ctk.CTkFrame(
            self.surface,
            fg_color=TABLE_PALETTE["table_alt"],
            corner_radius=18,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        self._nav_hud.place(relx=1.0, x=-18, y=18, anchor="ne")
        self._nav_status = ctk.CTkLabel(
            self._nav_hud,
            text="Desk 100%",
            text_color=TABLE_PALETTE["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._nav_status.grid(row=0, column=0, padx=(12, 10), pady=8, sticky="w")
        self._home_button = ctk.CTkButton(
            self._nav_hud,
            text="Home",
            width=72,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=self.jump_home,
        )
        self._home_button.grid(row=0, column=1, padx=(0, 8), pady=8)
        self._bookmark_button = ctk.CTkButton(
            self._nav_hud,
            text="Marks",
            width=78,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=self._show_bookmark_menu,
        )
        self._bookmark_button.grid(row=0, column=2, padx=(0, 10), pady=8)
        self._bookmark_menu = tk.Menu(self, tearoff=0)

        self._minimap_shell = ctk.CTkFrame(
            self.surface,
            width=MINIMAP_WIDTH,
            height=MINIMAP_HEIGHT,
            fg_color=TABLE_PALETTE["table_alt"],
            corner_radius=18,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        self._minimap_shell.place(relx=1.0, rely=1.0, x=-18, y=-18, anchor="se")
        self._minimap_shell.grid_propagate(False)
        self._minimap_title = ctk.CTkLabel(
            self._minimap_shell,
            text="Desk Map",
            text_color=TABLE_PALETTE["muted"],
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self._minimap_title.pack(anchor="w", padx=12, pady=(8, 4))
        self._minimap_canvas = tk.Canvas(
            self._minimap_shell,
            width=MINIMAP_WIDTH - 20,
            height=MINIMAP_HEIGHT - 34,
            bg=TABLE_PALETTE["panel_bg"],
            highlightthickness=0,
            bd=0,
        )
        self._minimap_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._minimap_canvas.bind("<Button-1>", self._on_minimap_click, add="+")

        self.tray = ctk.CTkFrame(
            self,
            fg_color=TABLE_PALETTE["table_alt"],
            corner_radius=20,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        self.tray.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.tray.grid_columnconfigure(1, weight=1)

        self.tray_label = ctk.CTkLabel(
            self.tray,
            text="Minimized",
            text_color=TABLE_PALETTE["muted"],
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.tray_label.grid(row=0, column=0, padx=(14, 10), pady=10, sticky="w")

        self.tray_buttons = ctk.CTkFrame(self.tray, fg_color="transparent")
        self.tray_buttons.grid(row=0, column=1, padx=(0, 12), pady=8, sticky="ew")

        self._empty_state = ctk.CTkLabel(
            self.surface,
            text="Use + Add Panel to start building the table.",
            text_color=TABLE_PALETTE["muted"],
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self._empty_state.place(relx=0.5, rely=0.5, anchor="center")
        self._bind_surface_navigation()
        self.bind("<Destroy>", self._handle_workspace_destroy, add="+")
        self._refresh_navigation_hud()
        self._refresh_minimap()
        self._refresh_minimized_tray()

    def _schedule_layout_changed(self) -> None:
        """Debounce layout persistence."""
        if self._disposed:
            return
        self._refresh_empty_state()
        self._refresh_minimized_tray()
        self._refresh_navigation_hud()
        self._refresh_minimap()
        if self._layout_changed_callback is None:
            return
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(180, self._flush_layout_changed)

    def _flush_layout_changed(self) -> None:
        """Emit the debounced layout change callback."""
        self._save_job = None
        if self._layout_changed_callback is not None:
            self._layout_changed_callback()

    def _refresh_empty_state(self, _event=None) -> None:
        """Toggle the instructional overlay."""
        if self._panels:
            self._empty_state.place_forget()
        else:
            self._empty_state.place(relx=0.5, rely=0.5, anchor="center")

    def _minimized_panel_ids(self) -> list[str]:
        """Return minimized panels in z-order."""
        return [
            panel_id
            for panel_id in self._z_order
            if panel_id in self._panels and self._panels[panel_id].layout_mode == "minimized"
        ]

    def _refresh_minimized_tray(self) -> None:
        """Refresh the minimized panel tray."""
        tray = getattr(self, "tray", None)
        buttons_frame = getattr(self, "tray_buttons", None)
        if tray is None or buttons_frame is None:
            return
        for child in buttons_frame.winfo_children():
            child.destroy()
        minimized_ids = self._minimized_panel_ids()
        if not minimized_ids:
            tray.grid_remove()
            return
        tray.grid()
        for panel_id in minimized_ids:
            definition = self._definitions.get(panel_id)
            if definition is None:
                continue
            ctk.CTkButton(
                buttons_frame,
                text=definition.title,
                height=30,
                fg_color=TABLE_PALETTE["table_chip"],
                hover_color="#283146",
                text_color=TABLE_PALETTE["text"],
                corner_radius=12,
                command=lambda value=panel_id: self.restore_panel(value),
            ).pack(side="left", padx=(0, 8))

    def _bind_surface_navigation(self) -> None:
        """Bind camera navigation to the empty table surface."""
        for widget in (self.surface, self._empty_state):
            widget.bind("<ButtonPress-1>", self._start_surface_pan, add="+")
            widget.bind("<B1-Motion>", self._pan_surface_to, add="+")
            widget.bind("<ButtonRelease-1>", self._stop_surface_pan, add="+")
            widget.bind("<Control-MouseWheel>", self._zoom_surface, add="+")
            widget.bind("<Button-1>", lambda _event: self.surface.focus_set(), add="+")
            widget.bind("<Home>", self._handle_home_shortcut, add="+")
        self._bind_workspace_middle_pan()
        try:
            self.surface.configure(cursor="fleur")
        except Exception:
            pass

    def _bind_workspace_middle_pan(self) -> None:
        """Bind middle-button camera pan to the containing window."""
        self._unbind_workspace_middle_pan()
        try:
            target = self.winfo_toplevel()
        except Exception:
            return
        if target is None:
            return
        binding_ids: dict[str, str] = {}
        for sequence, handler in (
            ("<ButtonPress-2>", self._start_surface_pan),
            ("<B2-Motion>", self._pan_surface_to),
            ("<ButtonRelease-2>", self._stop_surface_pan),
        ):
            try:
                binding_id = target.bind(sequence, handler, add="+")
            except Exception:
                continue
            if binding_id:
                binding_ids[sequence] = binding_id
        self._surface_pan_binding_target = target
        self._surface_pan_binding_ids = binding_ids

    def _unbind_workspace_middle_pan(self) -> None:
        """Remove any middle-button pan bindings registered on the window."""
        target = getattr(self, "_surface_pan_binding_target", None)
        binding_ids = dict(getattr(self, "_surface_pan_binding_ids", {}) or {})
        for sequence, binding_id in binding_ids.items():
            try:
                target.unbind(sequence, binding_id)
            except Exception:
                pass
        self._surface_pan_binding_target = None
        self._surface_pan_binding_ids = {}

    def _handle_workspace_destroy(self, event=None) -> None:
        """Release toplevel pan bindings when the workspace is destroyed."""
        if event is not None and getattr(event, "widget", None) is not self:
            return
        self._stop_surface_pan()
        self._unbind_workspace_middle_pan()

    def _widget_is_in_surface_subtree(self, widget) -> bool:
        """Return whether a widget belongs to this workspace surface."""
        surface = getattr(self, "surface", None)
        current = widget
        while current is not None:
            if current is surface:
                return True
            current = getattr(current, "master", None)
        return False

    def _camera_snapshot(self) -> dict[str, float]:
        """Return the current camera state."""
        return _normalize_camera(
            {
                "x": getattr(self, "_camera_x", 0.0),
                "y": getattr(self, "_camera_y", 0.0),
                "zoom": getattr(self, "_camera_zoom", 1.0),
            }
        )

    def _set_camera(self, *, x: float | None = None, y: float | None = None, zoom: float | None = None) -> None:
        """Apply camera changes and refresh projected overlays."""
        if x is not None:
            self._camera_x = round(_coerce_float(x), 2)
        if y is not None:
            self._camera_y = round(_coerce_float(y), 2)
        if zoom is not None:
            self._camera_zoom = _normalize_camera({"zoom": zoom})["zoom"]
        self.clear_snap_preview()
        self.clamp_panels()

    def _camera_view_size(self) -> tuple[float, float]:
        """Return the visible world-space viewport size."""
        surface_w, surface_h = self._surface_geometry()
        zoom = max(CAMERA_MIN_ZOOM, float(getattr(self, "_camera_zoom", 1.0)))
        return surface_w / zoom, surface_h / zoom

    def _screen_to_world(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        """Convert viewport-local screen coordinates into world coordinates."""
        zoom = max(CAMERA_MIN_ZOOM, float(getattr(self, "_camera_zoom", 1.0)))
        return (
            round(_coerce_float(getattr(self, "_camera_x", 0.0)) + (_coerce_float(screen_x) / zoom), 2),
            round(_coerce_float(getattr(self, "_camera_y", 0.0)) + (_coerce_float(screen_y) / zoom), 2),
        )

    def _screen_geometry_to_world(self, geometry: dict[str, int]) -> dict[str, float | int]:
        """Convert a viewport geometry into floating world geometry."""
        world_x, world_y = self._screen_to_world(int(geometry.get("x", 0)), int(geometry.get("y", 0)))
        return _normalize_floating_geometry(
            world_x,
            world_y,
            int(geometry.get("width", GMTablePanel.MIN_WIDTH)),
            int(geometry.get("height", GMTablePanel.MIN_HEIGHT)),
            min_width=GMTablePanel.MIN_WIDTH,
            min_height=GMTablePanel.MIN_HEIGHT,
        )

    def _project_floating_geometry(self, geometry: dict[str, float | int]) -> dict[str, int]:
        """Project a floating world geometry into viewport coordinates."""
        zoom = max(CAMERA_MIN_ZOOM, float(getattr(self, "_camera_zoom", 1.0)))
        camera_x = _coerce_float(getattr(self, "_camera_x", 0.0))
        camera_y = _coerce_float(getattr(self, "_camera_y", 0.0))
        return {
            "x": int(round((_coerce_float(geometry.get("x", 0.0)) - camera_x) * zoom)),
            "y": int(round((_coerce_float(geometry.get("y", 0.0)) - camera_y) * zoom)),
            "width": max(GMTablePanel.MIN_WIDTH, int(geometry.get("width", GMTablePanel.MIN_WIDTH))),
            "height": max(GMTablePanel.MIN_HEIGHT, int(geometry.get("height", GMTablePanel.MIN_HEIGHT))),
        }

    def _floating_geometry_snapshot(self, panel) -> dict[str, float | int]:
        """Return a floating geometry from a real or fake panel."""
        if hasattr(panel, "floating_geometry_snapshot"):
            return dict(panel.floating_geometry_snapshot())
        return dict(panel.geometry_snapshot())

    def _apply_floating_geometry(self, panel, geometry: dict[str, float | int]) -> None:
        """Apply a floating geometry to a real or fake panel."""
        if hasattr(panel, "apply_floating_geometry"):
            panel.apply_floating_geometry(geometry, screen_geometry=self._project_floating_geometry(geometry))
            return
        panel.apply_geometry(
            {
                "x": int(round(_coerce_float(geometry.get("x", 0.0)))),
                "y": int(round(_coerce_float(geometry.get("y", 0.0)))),
                "width": int(geometry.get("width", GMTablePanel.MIN_WIDTH)),
                "height": int(geometry.get("height", GMTablePanel.MIN_HEIGHT)),
            }
        )

    def _reproject_floating_panels(self) -> None:
        """Reproject floating panels through the current camera."""
        for panel in self._panels.values():
            if panel.layout_mode != "floating":
                continue
            self._apply_floating_geometry(panel, self._floating_geometry_snapshot(panel))

    def _refresh_navigation_hud(self) -> None:
        """Refresh camera affordances."""
        status = getattr(self, "_nav_status", None)
        if status is None:
            return
        zoom_percent = int(round(max(CAMERA_MIN_ZOOM, float(getattr(self, "_camera_zoom", 1.0))) * 100))
        status.configure(text=f"Desk {zoom_percent}%")

    def _refresh_minimap(self) -> None:
        """Redraw the desk minimap."""
        canvas = getattr(self, "_minimap_canvas", None)
        if canvas is None:
            return
        try:
            width = int(canvas.winfo_width())
            if width <= 1:
                width = int(canvas.cget("width"))
            height = int(canvas.winfo_height())
            if height <= 1:
                height = int(canvas.cget("height"))
        except Exception:
            width = MINIMAP_WIDTH - 20
            height = MINIMAP_HEIGHT - 34
        canvas.delete("all")

        viewport_w, viewport_h = self._camera_view_size()
        viewport = {
            "x": _coerce_float(getattr(self, "_camera_x", 0.0)),
            "y": _coerce_float(getattr(self, "_camera_y", 0.0)),
            "width": viewport_w,
            "height": viewport_h,
        }
        floating = [
            self._floating_geometry_snapshot(panel)
            for panel in self._panels.values()
            if panel.layout_mode == "floating"
        ]
        bounds = floating + [viewport]
        min_x = min(_coerce_float(item.get("x", 0.0)) for item in bounds)
        min_y = min(_coerce_float(item.get("y", 0.0)) for item in bounds)
        max_x = max(_coerce_float(item.get("x", 0.0)) + float(item.get("width", 0.0)) for item in bounds)
        max_y = max(_coerce_float(item.get("y", 0.0)) + float(item.get("height", 0.0)) for item in bounds)
        span_w = max(1.0, max_x - min_x)
        span_h = max(1.0, max_y - min_y)
        padding = 10.0
        scale = min((width - (padding * 2)) / span_w, (height - (padding * 2)) / span_h)
        scale = max(0.02, scale)
        self._minimap_projection = {
            "min_x": min_x,
            "min_y": min_y,
            "scale": scale,
            "padding": padding,
        }

        for geometry in floating:
            x0 = padding + ((_coerce_float(geometry["x"]) - min_x) * scale)
            y0 = padding + ((_coerce_float(geometry["y"]) - min_y) * scale)
            x1 = x0 + (float(geometry["width"]) * scale)
            y1 = y0 + (float(geometry["height"]) * scale)
            canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=TABLE_PALETTE["table_chip"],
                outline=TABLE_PALETTE["panel_border"],
                width=1,
            )

        x0 = padding + ((viewport["x"] - min_x) * scale)
        y0 = padding + ((viewport["y"] - min_y) * scale)
        x1 = x0 + (viewport["width"] * scale)
        y1 = y0 + (viewport["height"] * scale)
        canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline=TABLE_PALETTE["panel_focus"],
            width=2,
        )

    def _center_camera_on(self, world_x: float, world_y: float, *, zoom: float | None = None) -> None:
        """Center the viewport on a world point."""
        target_zoom = _normalize_camera({"zoom": zoom if zoom is not None else self._camera_zoom})["zoom"]
        surface_w, surface_h = self._surface_geometry()
        self._set_camera(
            x=_coerce_float(world_x) - (surface_w / (2 * target_zoom)),
            y=_coerce_float(world_y) - (surface_h / (2 * target_zoom)),
            zoom=target_zoom,
        )

    def _start_surface_pan(self, event) -> None:
        """Start panning the infinite desk."""
        widget = getattr(event, "widget", None)
        is_middle_button = int(getattr(event, "num", 0) or 0) == 2
        if widget is not self.surface and widget is not self._empty_state:
            if not is_middle_button or not self._widget_is_in_surface_subtree(widget):
                return
        self.surface.focus_set()
        self._pan_origin = (
            event.x_root,
            event.y_root,
            _coerce_float(getattr(self, "_camera_x", 0.0)),
            _coerce_float(getattr(self, "_camera_y", 0.0)),
        )

    def _pan_surface_to(self, event) -> None:
        """Pan the camera with the active drag gesture."""
        if self._pan_origin is None:
            return
        root_x, root_y, start_x, start_y = self._pan_origin
        zoom = max(CAMERA_MIN_ZOOM, float(getattr(self, "_camera_zoom", 1.0)))
        self._set_camera(
            x=start_x - ((event.x_root - root_x) / zoom),
            y=start_y - ((event.y_root - root_y) / zoom),
        )

    def _stop_surface_pan(self, _event=None) -> None:
        """Finish a camera pan gesture."""
        self._pan_origin = None

    def _zoom_surface(self, event) -> None:
        """Zoom the desk around the cursor position."""
        try:
            screen_x = int(event.x)
            screen_y = int(event.y)
        except Exception:
            screen_x = 0
            screen_y = 0
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        delta = 1 if int(getattr(event, "delta", 0)) > 0 else -1
        target_zoom = max(
            CAMERA_MIN_ZOOM,
            min(CAMERA_MAX_ZOOM, float(getattr(self, "_camera_zoom", 1.0)) + (delta * CAMERA_ZOOM_STEP)),
        )
        self._set_camera(
            x=world_x - (screen_x / target_zoom),
            y=world_y - (screen_y / target_zoom),
            zoom=target_zoom,
        )

    def _handle_home_shortcut(self, _event=None) -> str:
        """Return to the saved home view."""
        self.jump_home()
        return "break"

    def list_bookmarks(self) -> list[dict[str, object]]:
        """Return lightweight desk bookmarks."""
        return [dict(bookmark) for bookmark in getattr(self, "_bookmarks", [])]

    def set_home_camera(self) -> None:
        """Set the current viewport as the workspace home."""
        self._home_camera = self._camera_snapshot()
        self._schedule_layout_changed()

    def jump_home(self) -> None:
        """Return to the saved home camera."""
        home = _normalize_camera(getattr(self, "_home_camera", None))
        self._set_camera(x=home["x"], y=home["y"], zoom=home["zoom"])

    def save_bookmark(self, name: str) -> None:
        """Create or update a named camera bookmark."""
        bookmark = _normalize_bookmark(name, self._camera_snapshot())
        lookup = bookmark["name"].strip().casefold()
        for index, existing in enumerate(getattr(self, "_bookmarks", [])):
            if str(existing.get("name") or "").strip().casefold() == lookup:
                self._bookmarks[index] = bookmark
                self._schedule_layout_changed()
                return
        self._bookmarks = list(getattr(self, "_bookmarks", [])) + [bookmark]
        self._schedule_layout_changed()

    def delete_bookmark(self, name: str) -> None:
        """Delete a bookmark by name."""
        lookup = str(name or "").strip().casefold()
        self._bookmarks = [
            bookmark
            for bookmark in getattr(self, "_bookmarks", [])
            if str(bookmark.get("name") or "").strip().casefold() != lookup
        ]
        self._schedule_layout_changed()

    def jump_to_bookmark(self, name: str) -> None:
        """Jump to a stored camera bookmark."""
        lookup = str(name or "").strip().casefold()
        for bookmark in getattr(self, "_bookmarks", []):
            if str(bookmark.get("name") or "").strip().casefold() != lookup:
                continue
            target = _normalize_camera(bookmark)
            self._set_camera(x=target["x"], y=target["y"], zoom=target["zoom"])
            break

    def _prompt_bookmark_name(self) -> str | None:
        """Prompt for a bookmark name."""
        return simpledialog.askstring("GM Table Bookmark", "Bookmark name:", parent=self.winfo_toplevel())

    def _save_bookmark_from_prompt(self) -> None:
        """Create or update a bookmark from a prompt."""
        name = self._prompt_bookmark_name()
        if name:
            self.save_bookmark(name)

    def _show_bookmark_menu(self) -> None:
        """Open the bookmark camera menu."""
        menu = getattr(self, "_bookmark_menu", None)
        button = getattr(self, "_bookmark_button", None)
        if menu is None or button is None:
            return
        menu.delete(0, "end")
        menu.add_command(label="Jump Home", command=self.jump_home)
        menu.add_command(label="Set Current View As Home", command=self.set_home_camera)
        menu.add_separator()
        menu.add_command(label="Add Or Update Bookmark...", command=self._save_bookmark_from_prompt)
        if getattr(self, "_bookmarks", []):
            jump_menu = tk.Menu(menu, tearoff=0)
            delete_menu = tk.Menu(menu, tearoff=0)
            for bookmark in getattr(self, "_bookmarks", []):
                name = str(bookmark.get("name") or "Bookmark")
                jump_menu.add_command(label=name, command=lambda value=name: self.jump_to_bookmark(value))
                delete_menu.add_command(label=name, command=lambda value=name: self.delete_bookmark(value))
            menu.add_cascade(label="Jump To Bookmark", menu=jump_menu)
            menu.add_cascade(label="Delete Bookmark", menu=delete_menu)
        else:
            menu.add_command(label="No Bookmarks Yet", state="disabled")
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _on_minimap_click(self, event) -> None:
        """Recenter the viewport from the minimap."""
        projection = getattr(self, "_minimap_projection", None)
        if not projection:
            return
        world_x = projection["min_x"] + ((float(event.x) - projection["padding"]) / projection["scale"])
        world_y = projection["min_y"] + ((float(event.y) - projection["padding"]) / projection["scale"])
        self._center_camera_on(world_x, world_y)

    def _on_surface_configure(self, _event=None) -> None:
        """Keep docked panels aligned when the workspace changes size."""
        self._refresh_empty_state()
        if self._disposed:
            return
        if self._surface_resize_job is not None:
            try:
                self.after_cancel(self._surface_resize_job)
            except Exception:
                pass
        self._surface_resize_job = self.after(90, self._handle_surface_resize)

    def _handle_surface_resize(self) -> None:
        """Refresh panel bounds after the surface settles."""
        self._surface_resize_job = None
        if self._disposed:
            return
        self.clear_snap_preview()
        self.clamp_panels()

    def _apply_focus_state(self, panel_id: str | None) -> None:
        """Refresh visual focus across all panels."""
        for current_id, panel in self._panels.items():
            is_target = current_id == panel_id and panel.layout_mode != "minimized"
            panel.set_focus_state(is_target)
            if is_target:
                panel.lift()

    def _visible_panel_ids(self) -> list[str]:
        """Return visible panels in z-order."""
        return [
            panel_id
            for panel_id in self._z_order
            if panel_id in self._panels and self._panels[panel_id].layout_mode != "minimized"
        ]

    def _last_visible_panel_id(self, *, exclude: str | None = None) -> str | None:
        """Return the topmost visible panel other than an optional exclusion."""
        for panel_id in reversed(self._z_order):
            if panel_id == exclude:
                continue
            panel = self._panels.get(panel_id)
            if panel is not None and panel.layout_mode != "minimized":
                return panel_id
        return None

    def _surface_geometry(self) -> tuple[int, int]:
        """Return stable workspace dimensions."""
        self.update_idletasks()
        return _surface_dimensions(self.surface)

    def list_panels(
        self,
        *,
        kinds: set[str] | None = None,
        include_minimized: bool = True,
    ) -> list[dict[str, object]]:
        """Return panel records in z-order."""
        records: list[dict[str, object]] = []
        for panel_id in self._z_order:
            panel = self._panels.get(panel_id)
            definition = self._definitions.get(panel_id)
            if panel is None or definition is None:
                continue
            if kinds is not None and definition.kind not in kinds:
                continue
            if not include_minimized and panel.layout_mode == "minimized":
                continue
            records.append(
                {
                    "panel_id": panel_id,
                    "panel": panel,
                    "definition": definition,
                    "payload": self._panel_payloads.get(panel_id),
                    "layout_mode": panel.layout_mode,
                }
            )
        return records

    def get_active_panel_id(
        self,
        *,
        kinds: set[str] | None = None,
        include_minimized: bool = False,
    ) -> str | None:
        """Return the topmost panel id matching an optional kind filter."""
        for panel_id in reversed(self._z_order):
            panel = self._panels.get(panel_id)
            definition = self._definitions.get(panel_id)
            if panel is None or definition is None:
                continue
            if kinds is not None and definition.kind not in kinds:
                continue
            if not include_minimized and panel.layout_mode == "minimized":
                continue
            return panel_id
        return None

    def get_panel_payload(self, panel_id: str) -> object | None:
        """Return the hosted payload for a panel."""
        return self._panel_payloads.get(panel_id)

    def get_panel_definition(self, panel_id: str) -> PanelDefinition | None:
        """Return a panel definition."""
        return self._definitions.get(panel_id)

    def bring_to_front(self, panel_id: str) -> None:
        """Focus a panel and raise it visually."""
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        if panel.layout_mode == "minimized":
            self.restore_panel(panel_id, focus=False)
            panel = self._panels.get(panel_id)
            if panel is None:
                return
        self._z_order = [value for value in self._z_order if value != panel_id] + [panel_id]
        self._apply_focus_state(panel_id)
        if getattr(self, "_snap_preview_mode", None) is not None:
            preview = getattr(self, "_snap_preview", None)
            if preview is not None:
                preview.lift()
            panel.lift()
        self._schedule_layout_changed()

    def remove_panel(self, panel_id: str) -> None:
        """Close a panel."""
        panel = self._panels.pop(panel_id, None)
        self._definitions.pop(panel_id, None)
        self._z_order = [value for value in self._z_order if value != panel_id]
        payload = self._panel_payloads.pop(panel_id, None)
        if payload is not None and hasattr(payload, "close"):
            try:
                payload.close()
            except Exception:
                pass
        if panel is not None:
            panel.destroy()
        self.clear_snap_preview()
        self._apply_focus_state(self._last_visible_panel_id())
        self._schedule_layout_changed()

    def clear(self) -> None:
        """Remove every panel."""
        for panel_id in list(self._panels.keys()):
            self.remove_panel(panel_id)

    def dispose(self) -> None:
        """Close every hosted payload without emitting more layout work."""
        self._disposed = True
        self._layout_changed_callback = None
        self._stop_surface_pan()
        self._unbind_workspace_middle_pan()
        self.clear_snap_preview()
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
            self._save_job = None
        if self._surface_resize_job is not None:
            try:
                self.after_cancel(self._surface_resize_job)
            except Exception:
                pass
            self._surface_resize_job = None
        for panel_id in list(self._panels.keys()):
            self.remove_panel(panel_id)

    def add_panel(self, definition: PanelDefinition, *, geometry: dict | None = None) -> GMTablePanel:
        """Create and place a new floating panel."""
        width, height = resolve_default_panel_size(definition.kind, definition.state)
        world_geometry = self._suggest_position(width=width, height=height)
        if geometry:
            world_geometry = _world_geometry_from_state(
                geometry,
                default_x=world_geometry["x"],
                default_y=world_geometry["y"],
                default_width=int(geometry.get("width", width)),
                default_height=int(geometry.get("height", height)),
                min_width=GMTablePanel.MIN_WIDTH,
                min_height=GMTablePanel.MIN_HEIGHT,
            )
        width = int(world_geometry["width"])
        height = int(world_geometry["height"])
        panel = GMTablePanel(
            self.surface,
            definition=definition,
            width=width,
            height=height,
            on_focus=self.bring_to_front,
            on_close=self.remove_panel,
            on_geometry_changed=lambda _panel_id: self._schedule_layout_changed(),
            project_floating_geometry=self._project_floating_geometry,
            screen_to_world=self._screen_to_world,
            get_camera_zoom=lambda: self._camera_zoom,
            on_snap_requested=self.snap_panel,
            on_snap_preview_changed=self.preview_snap_target,
            on_toggle_maximize=self.toggle_panel_maximize,
            on_window_action=self.handle_window_action,
        )
        self._apply_floating_geometry(panel, world_geometry)
        panel_payload = self._build_panel(panel.body, definition)
        self._mount_payload_widget(panel.body, panel_payload)
        self._panels[definition.panel_id] = panel
        self._definitions[definition.panel_id] = definition
        self._panel_payloads[definition.panel_id] = panel_payload
        self._z_order.append(definition.panel_id)
        self.bring_to_front(definition.panel_id)
        self._schedule_layout_changed()
        return panel

    def _mount_payload_widget(self, host: ctk.CTkFrame, payload: object) -> None:
        """Grid widget payloads that are returned directly by builders."""
        if not isinstance(payload, tk.Widget):
            return
        try:
            if payload.master is not host:
                return
        except Exception:
            return
        try:
            manager = payload.winfo_manager()
        except Exception:
            manager = ""
        if manager:
            return
        payload.grid(row=0, column=0, sticky="nsew")

    def handle_window_action(self, panel_id: str, action: str) -> None:
        """Dispatch a panel window action."""
        if action.startswith("snap:"):
            self.snap_panel(panel_id, action.split(":", 1)[1])
            return
        if action == "restore":
            self.restore_panel(panel_id)
            return
        if action == "minimize":
            self.minimize_panel(panel_id)
            return
        if action == "toggle_maximize":
            self.toggle_panel_maximize(panel_id)
            return
        if action == "snap_left":
            self.snap_panel(panel_id, "left")
            return
        if action == "snap_right":
            self.snap_panel(panel_id, "right")
            return
        if action == "close_others":
            self.close_other_panels(panel_id)
            return
        if action == "cascade_all":
            self.cascade_panels()
            return
        if action == "tile_all":
            self.auto_arrange()
            return
        if action == "restore_all":
            self.restore_all_panels()
            return

    def preview_snap_target(self, panel_id: str, mode: str | None) -> None:
        """Show or hide the live snap preview while a panel is being dragged."""
        if mode is None or mode not in SNAP_LAYOUT_MODES:
            self.clear_snap_preview()
            return
        preview = getattr(self, "_snap_preview", None)
        label = getattr(self, "_snap_preview_label", None)
        if preview is None or label is None:
            return
        surface_w, surface_h = _surface_dimensions(self.surface)
        geometry = _snap_geometry(
            mode,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=GMTablePanel.MIN_WIDTH,
            min_height=GMTablePanel.MIN_HEIGHT,
        )
        self._snap_preview_mode = mode
        label.configure(text=SNAP_MODE_LABELS.get(mode, "Snap"))
        preview.configure(width=geometry["width"], height=geometry["height"])
        preview.place(x=geometry["x"], y=geometry["y"])
        preview.lift()
        panel = self._panels.get(panel_id)
        if panel is not None:
            panel.lift()

    def clear_snap_preview(self) -> None:
        """Hide the magnetic snap preview overlay."""
        self._snap_preview_mode = None
        preview = getattr(self, "_snap_preview", None)
        if preview is not None:
            preview.place_forget()

    def resize_panel(self, panel_id: str, width: int, height: int) -> None:
        """Resize an existing panel and keep it visible."""
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        geometry = self._floating_geometry_snapshot(panel)
        geometry = _normalize_floating_geometry(
            geometry["x"],
            geometry["y"],
            int(width),
            int(height),
            min_width=GMTablePanel.MIN_WIDTH,
            min_height=GMTablePanel.MIN_HEIGHT,
        )
        panel.clear_layout_mode()
        self._apply_floating_geometry(panel, geometry)
        self.bring_to_front(panel_id)

    def ensure_panel_minimum_size(self, panel_id: str, width: int, height: int) -> None:
        """Grow a panel only when it is below a readable minimum size."""
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        current_geometry = panel.geometry_snapshot()
        current_width = max(GMTablePanel.MIN_WIDTH, int(current_geometry["width"]))
        current_height = max(GMTablePanel.MIN_HEIGHT, int(current_geometry["height"]))
        target_width = max(current_width, int(width))
        target_height = max(current_height, int(height))
        if target_width == current_width and target_height == current_height:
            return
        self.resize_panel(panel_id, target_width, target_height)

    def _suggest_position(self, *, width: int, height: int) -> dict[str, float | int]:
        """Return a cascading default position for a new panel."""
        index = len(self._panels)
        surface_w, surface_h = self._surface_geometry()
        zoom = max(CAMERA_MIN_ZOOM, float(self._camera_zoom))
        center_screen_x = max(PANEL_MARGIN, int((surface_w - int(width)) / 2))
        center_screen_y = max(PANEL_MARGIN, int((surface_h - int(height)) / 2))
        return _normalize_floating_geometry(
            self._camera_x + ((center_screen_x + ((index * 28) % 280)) / zoom),
            self._camera_y + ((center_screen_y + ((index * 24) % 220)) / zoom),
            width,
            height,
            min_width=GMTablePanel.MIN_WIDTH,
            min_height=GMTablePanel.MIN_HEIGHT,
        )

    def _find_snap_companion(self, panel_id: str) -> str | None:
        """Return the next visible panel that should pair with a snapped panel."""
        for candidate_id in reversed(self._z_order):
            if candidate_id == panel_id:
                continue
            candidate = self._panels.get(candidate_id)
            if candidate is None or candidate.layout_mode == "minimized":
                continue
            return candidate_id
        return None

    def minimize_panel(self, panel_id: str) -> None:
        """Minimize a panel into the workspace tray."""
        panel = self._panels.get(panel_id)
        if panel is None or panel.layout_mode == "minimized":
            return
        panel.minimize()
        self._apply_focus_state(self._last_visible_panel_id(exclude=panel_id))
        self._schedule_layout_changed()

    def restore_panel(self, panel_id: str, *, focus: bool = True) -> None:
        """Restore a minimized, snapped, or maximized panel."""
        self.clear_snap_preview()
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        if panel.layout_mode == "minimized":
            surface_w, surface_h = self._surface_geometry()
            if not panel.restore_from_minimized(surface_w=surface_w, surface_h=surface_h):
                return
            self._schedule_layout_changed()
            if focus:
                self.bring_to_front(panel_id)
            else:
                self._apply_focus_state(self.get_active_panel_id())
            return
        if panel.layout_mode in SNAP_LAYOUT_MODES and panel.restore_layout():
            self._schedule_layout_changed()
            if focus:
                self.bring_to_front(panel_id)
            else:
                self._apply_focus_state(self.get_active_panel_id())
            return
        if focus:
            self.bring_to_front(panel_id)

    def restore_all_panels(self) -> None:
        """Restore every minimized panel."""
        self.clear_snap_preview()
        restored_any = False
        surface_w, surface_h = self._surface_geometry()
        for panel_id in list(self._minimized_panel_ids()):
            panel = self._panels.get(panel_id)
            if panel is None:
                continue
            restored_any = panel.restore_from_minimized(surface_w=surface_w, surface_h=surface_h) or restored_any
        if restored_any:
            active = self.get_active_panel_id()
            self._apply_focus_state(active)
            self._schedule_layout_changed()

    def close_other_panels(self, panel_id: str) -> None:
        """Close every panel except the target panel."""
        for candidate_id in list(self._z_order):
            if candidate_id != panel_id:
                self.remove_panel(candidate_id)
        if panel_id in self._panels:
            self.bring_to_front(panel_id)

    def snap_panel(self, panel_id: str, mode: str) -> None:
        """Snap a panel to the workspace edges like a desktop window."""
        if mode not in SNAP_LAYOUT_MODES:
            return
        self.clear_snap_preview()
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        if panel.layout_mode == "minimized":
            self.restore_panel(panel_id, focus=False)
            panel = self._panels.get(panel_id)
            if panel is None:
                return
        surface_w, surface_h = self._surface_geometry()
        geometry = _snap_geometry(
            mode,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=GMTablePanel.MIN_WIDTH,
            min_height=GMTablePanel.MIN_HEIGHT,
        )
        panel.enter_layout_mode(mode, geometry)
        companion_mode = SNAP_COMPLEMENT_MODES.get(mode)
        if companion_mode is not None:
            companion_id = self._find_snap_companion(panel_id)
            if companion_id is not None:
                companion = self._panels.get(companion_id)
                if companion is not None:
                    companion.enter_layout_mode(
                        companion_mode,
                        _snap_geometry(
                            companion_mode,
                            surface_w=surface_w,
                            surface_h=surface_h,
                            min_width=GMTablePanel.MIN_WIDTH,
                            min_height=GMTablePanel.MIN_HEIGHT,
                        ),
                    )
        self.bring_to_front(panel_id)

    def toggle_panel_maximize(self, panel_id: str) -> None:
        """Toggle maximize or restore from a panel header."""
        self.clear_snap_preview()
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        if panel.layout_mode == "minimized":
            self.restore_panel(panel_id, focus=False)
            panel = self._panels.get(panel_id)
            if panel is None:
                return
        if panel.layout_mode == "maximize":
            self.restore_panel(panel_id)
            return
        if panel.layout_mode in (SNAP_LAYOUT_MODES - {"maximize"}) and panel.restore_layout():
            self.bring_to_front(panel_id)
            return
        surface_w, surface_h = self._surface_geometry()
        panel.enter_layout_mode(
            "maximize",
            _snap_geometry(
                "maximize",
                surface_w=surface_w,
                surface_h=surface_h,
                min_width=GMTablePanel.MIN_WIDTH,
                min_height=GMTablePanel.MIN_HEIGHT,
            ),
        )
        self.bring_to_front(panel_id)

    def auto_arrange(self) -> None:
        """Tile visible panels across the surface."""
        visible_ids = self._visible_panel_ids()
        if not visible_ids:
            return
        self.update_idletasks()
        surface_w = max(960, self.surface.winfo_width())
        surface_h = max(640, self.surface.winfo_height())
        margin = 24
        gutter = 18
        max_width = max(GMTablePanel.MIN_WIDTH, surface_w - (margin * 2))
        max_height = max(GMTablePanel.MIN_HEIGHT, surface_h - (margin * 2))
        x = margin
        y = margin
        row_height = 0
        for panel_id in visible_ids:
            panel = self._panels.get(panel_id)
            definition = self._definitions.get(panel_id)
            if panel is None:
                continue
            preferred_width, preferred_height = resolve_default_panel_size(
                definition.kind if definition is not None else "entity",
                definition.state if definition is not None else None,
            )
            geometry = panel.geometry_snapshot()
            width = _clamp(
                max(int(geometry["width"]), int(preferred_width)),
                GMTablePanel.MIN_WIDTH,
                max_width,
            )
            height = _clamp(
                max(int(geometry["height"]), int(preferred_height)),
                GMTablePanel.MIN_HEIGHT,
                max_height,
            )
            if x > margin and (x + width) > (surface_w - margin):
                x = margin
                y += row_height + gutter
                row_height = 0
            panel.clear_layout_mode()
            self._apply_floating_geometry(
                panel,
                self._screen_geometry_to_world({"x": x, "y": y, "width": width, "height": height}),
            )
            row_height = max(row_height, height)
            x += width + gutter
        self._schedule_layout_changed()

    def cascade_panels(self) -> None:
        """Cascade visible panels diagonally like classic desktop windows."""
        visible_ids = self._visible_panel_ids()
        if not visible_ids:
            return
        surface_w, surface_h = self._surface_geometry()
        margin = 26
        offset = 34
        width = _clamp(int(surface_w * 0.72), GMTablePanel.MIN_WIDTH, surface_w - (margin * 2))
        height = _clamp(int(surface_h * 0.72), GMTablePanel.MIN_HEIGHT, surface_h - (margin * 2))
        max_x = max(margin, surface_w - width - margin)
        max_y = max(margin, surface_h - height - margin)
        for index, panel_id in enumerate(visible_ids):
            panel = self._panels.get(panel_id)
            if panel is None:
                continue
            x = min(margin + (index * offset), max_x)
            y = min(margin + (index * offset), max_y)
            panel.clear_layout_mode()
            self._apply_floating_geometry(
                panel,
                self._screen_geometry_to_world({"x": x, "y": y, "width": width, "height": height}),
            )
        self._apply_focus_state(visible_ids[-1])
        self._schedule_layout_changed()

    def clamp_panels(self) -> None:
        """Reproject floating panels and keep snapped panels viewport-relative."""
        self.update_idletasks()
        surface_w, surface_h = _surface_dimensions(self.surface)
        for panel in self._panels.values():
            if panel.layout_mode == "minimized":
                continue
            if panel.layout_mode in SNAP_LAYOUT_MODES:
                panel.apply_geometry(
                    _snap_geometry(
                        panel.layout_mode,
                        surface_w=surface_w,
                        surface_h=surface_h,
                        min_width=GMTablePanel.MIN_WIDTH,
                        min_height=GMTablePanel.MIN_HEIGHT,
                    )
                )
                continue
            self._apply_floating_geometry(panel, self._floating_geometry_snapshot(panel))
        self._schedule_layout_changed()

    def serialize(self) -> dict[str, object]:
        """Return a serializable workspace snapshot."""
        panels: list[dict[str, object]] = []
        for order, panel_id in enumerate(self._z_order, start=1):
            panel = self._panels.get(panel_id)
            definition = self._definitions.get(panel_id)
            payload = self._panel_payloads.get(panel_id)
            if panel is None or definition is None:
                continue
            snapshot = dict(definition.state or {})
            floating_geometry = self._floating_geometry_snapshot(panel)
            snapshot.update(
                {
                    "world_x": floating_geometry["x"],
                    "world_y": floating_geometry["y"],
                    "width": floating_geometry["width"],
                    "height": floating_geometry["height"],
                }
            )
            snapshot["z"] = order
            snapshot.update(panel.serialize_layout_state())
            if payload is not None and hasattr(payload, "get_state"):
                try:
                    dynamic_state = payload.get_state() or {}
                    if isinstance(dynamic_state, dict):
                        snapshot.update(dynamic_state)
                except Exception:
                    pass
            panels.append(
                {
                    "panel_id": definition.panel_id,
                    "kind": definition.kind,
                    "title": definition.title,
                    "state": snapshot,
                }
            )
        return {
            "camera": self._camera_snapshot(),
            "home_camera": dict(getattr(self, "_home_camera", self._camera_snapshot())),
            "bookmarks": [dict(bookmark) for bookmark in getattr(self, "_bookmarks", [])],
            "panels": panels,
        }

    def restore(self, layout: dict[str, object] | None) -> None:
        """Hydrate panels from a saved layout."""
        payload = layout if isinstance(layout, dict) else {}
        self.clear()
        camera = _normalize_camera(payload.get("camera"))
        self._camera_x = camera["x"]
        self._camera_y = camera["y"]
        self._camera_zoom = camera["zoom"]
        home_camera = payload.get("home_camera")
        self._home_camera = _normalize_camera(home_camera if isinstance(home_camera, dict) else camera)
        self._bookmarks = [
            _normalize_bookmark(str(bookmark.get("name") or "Bookmark"), bookmark)
            for bookmark in list(payload.get("bookmarks") or [])
            if isinstance(bookmark, dict)
        ]
        panels = [item for item in list(payload.get("panels") or []) if isinstance(item, dict)]
        panels.sort(key=lambda item: int((item.get("state") or {}).get("z", 0)))
        for item in panels:
            state = dict(item.get("state") or {})
            definition = PanelDefinition(
                panel_id=str(item.get("panel_id") or ""),
                kind=str(item.get("kind") or "entity"),
                title=str(item.get("title") or "Panel"),
                state=_payload_state(state),
            )
            if not definition.panel_id:
                continue
            world_geometry = _world_geometry_from_state(
                state,
                default_width=DEFAULT_PANEL_SIZES.get(definition.kind, DEFAULT_PANEL_SIZES["entity"])[0],
                default_height=DEFAULT_PANEL_SIZES.get(definition.kind, DEFAULT_PANEL_SIZES["entity"])[1],
                min_width=GMTablePanel.MIN_WIDTH,
                min_height=GMTablePanel.MIN_HEIGHT,
            )
            panel = self.add_panel(definition, geometry=world_geometry)
            restore_geometry = state.get("restore_geometry")
            if isinstance(restore_geometry, dict):
                panel._restore_geometry = _world_geometry_from_state(
                    restore_geometry,
                    default_x=world_geometry["x"],
                    default_y=world_geometry["y"],
                    default_width=int(world_geometry["width"]),
                    default_height=int(world_geometry["height"]),
                    min_width=GMTablePanel.MIN_WIDTH,
                    min_height=GMTablePanel.MIN_HEIGHT,
                )
            else:
                panel._restore_geometry = dict(world_geometry)
            layout_mode = str(state.get("layout_mode") or "floating")
            panel._minimized_restore_mode = str(state.get("minimized_restore_mode") or "floating")
            if layout_mode == "minimized":
                panel._layout_mode = "minimized"
                panel.place_forget()
                panel._refresh_window_controls()
            elif layout_mode in SNAP_LAYOUT_MODES:
                surface_w, surface_h = self._surface_geometry()
                panel._layout_mode = layout_mode
                panel.apply_geometry(
                    _snap_geometry(
                        layout_mode,
                        surface_w=surface_w,
                        surface_h=surface_h,
                        min_width=GMTablePanel.MIN_WIDTH,
                        min_height=GMTablePanel.MIN_HEIGHT,
                    )
                )
                panel._refresh_window_controls()
        self.clamp_panels()
