"""Floating workspace primitives for the GM Table."""

from __future__ import annotations

import tkinter as tk
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
VISIBLE_LAYOUT_MODES = {"floating", "left", "right", "maximize"}
WORKSPACE_STATE_KEYS = {
    "height",
    "layout_mode",
    "minimized_restore_mode",
    "restore_geometry",
    "width",
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


def _snap(value: int, grid: int = 24) -> int:
    """Snap a value to the nearest grid slot."""
    if grid <= 1:
        return value
    return int(round(value / grid) * grid)


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
    threshold: int = PANEL_SNAP_THRESHOLD,
) -> str | None:
    """Return the Windows-like snap target under the pointer."""
    if int(pointer_y) <= threshold:
        return "maximize"
    if int(pointer_x) <= threshold:
        return "left"
    if int(pointer_x) >= int(surface_w) - threshold:
        return "right"
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
    if mode == "maximize":
        return _constrain_panel_geometry(
            margin,
            margin,
            int(surface_w) - (margin * 2),
            int(surface_h) - (margin * 2),
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
            margin=margin,
        )

    if mode not in {"left", "right"}:
        raise ValueError(f"Unsupported snap mode: {mode}")

    usable_width = max(min_width * 2, int(surface_w) - (margin * 2) - gutter)
    half_width = max(min_width, usable_width // 2)
    x = margin if mode == "left" else int(surface_w) - margin - half_width
    return _constrain_panel_geometry(
        x,
        margin,
        half_width,
        int(surface_h) - (margin * 2),
        surface_w=surface_w,
        surface_h=surface_h,
        min_width=min_width,
        min_height=min_height,
        margin=margin,
    )


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
        on_snap_requested: Callable[[str, str], None],
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
        self._on_snap_requested = on_snap_requested
        self._on_toggle_maximize = on_toggle_maximize
        self._on_window_action = on_window_action
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._resize_origin: tuple[int, int, dict[str, int], str] | None = None
        self._restore_geometry: dict[str, int] | None = None
        self._layout_mode = "floating"
        self._minimized_restore_mode = "floating"
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
            self._restore_geometry = self.geometry_snapshot()
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
            geometry["x"] = int(round((int(anchor_x_root) - surface_root_x) - (restore_width * pointer_ratio_x)))
            geometry["y"] = int(round((int(anchor_y_root) - surface_root_y) - (restore_height * pointer_ratio_y)))
        surface_w, surface_h = _surface_dimensions(self.master)
        constrained = _constrain_panel_geometry(
            int(geometry.get("x", self.winfo_x())),
            int(geometry.get("y", self.winfo_y())),
            int(geometry.get("width", self.winfo_width())),
            int(geometry.get("height", self.winfo_height())),
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self._layout_mode = "floating"
        self._minimized_restore_mode = "floating"
        self.apply_geometry(constrained)
        self._refresh_window_controls()
        return True

    def minimize(self) -> None:
        """Hide the panel and remember how it should restore."""
        if self._layout_mode == "minimized":
            return
        restore_mode = self._layout_mode if self._layout_mode in VISIBLE_LAYOUT_MODES else "floating"
        if restore_mode == "floating":
            self._restore_geometry = self.geometry_snapshot()
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
            geometry = dict(self._restore_geometry or self._current_geometry)
            geometry = _constrain_panel_geometry(
                int(geometry.get("x", 24)),
                int(geometry.get("y", 24)),
                int(geometry.get("width", self.MIN_WIDTH)),
                int(geometry.get("height", self.MIN_HEIGHT)),
                surface_w=surface_w,
                surface_h=surface_h,
                min_width=self.MIN_WIDTH,
                min_height=self.MIN_HEIGHT,
            )
            self._layout_mode = "floating"
            self.apply_geometry(geometry)
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

    def serialize_layout_state(self) -> dict[str, object]:
        """Return panel layout metadata for persistence."""
        payload: dict[str, object] = {"layout_mode": self._layout_mode}
        if self._restore_geometry:
            payload["restore_geometry"] = dict(self._restore_geometry)
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
        maximize_label = "Restore Size" if self._layout_mode in {"left", "right", "maximize"} else "Maximize"
        menu.add_command(label=maximize_label, command=lambda: self._dispatch_window_action("toggle_maximize"))
        menu.add_separator()
        menu.add_command(label="Snap Left", command=lambda: self._dispatch_window_action("snap_left"))
        menu.add_command(label="Snap Right", command=lambda: self._dispatch_window_action("snap_right"))
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
        maximize_label = "Restore" if self._layout_mode in {"left", "right", "maximize"} else "Max"
        self.maximize_button.configure(text=maximize_label)

    def _start_drag(self, event) -> None:
        """Start moving a panel."""
        if self._layout_mode == "minimized":
            return
        self._on_focus(self.definition.panel_id)
        if self._layout_mode != "floating":
            self.restore_layout(anchor_x_root=event.x_root, anchor_y_root=event.y_root)
        self._drag_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def _drag_to(self, event) -> None:
        """Move the panel with the pointer."""
        if self._drag_origin is None:
            return
        root_x, root_y, start_x, start_y = self._drag_origin
        surface_w, surface_h = _surface_dimensions(self.master)
        geometry = _constrain_panel_geometry(
            start_x + (event.x_root - root_x),
            start_y + (event.y_root - root_y),
            self.winfo_width(),
            self.winfo_height(),
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.place_configure(x=geometry["x"], y=geometry["y"])
        self._current_geometry["x"] = geometry["x"]
        self._current_geometry["y"] = geometry["y"]

    def _stop_drag(self, event=None) -> None:
        """Stop dragging and snap to the workspace grid."""
        if self._drag_origin is None:
            return
        self._drag_origin = None
        if event is not None:
            try:
                pointer_x = int(event.x_root) - int(self.master.winfo_rootx())
                pointer_y = int(event.y_root) - int(self.master.winfo_rooty())
                surface_w, _surface_h = _surface_dimensions(self.master)
                snap_mode = _resolve_snap_mode(pointer_x, pointer_y, surface_w=surface_w)
            except Exception:
                snap_mode = None
            if snap_mode is not None:
                self._on_snap_requested(self.definition.panel_id, snap_mode)
                return
        surface_w, surface_h = _surface_dimensions(self.master)
        geometry = _constrain_panel_geometry(
            _snap(self.winfo_x()),
            _snap(self.winfo_y()),
            self.winfo_width(),
            self.winfo_height(),
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.clear_layout_mode()
        self.apply_geometry(geometry)
        self._on_geometry_changed(self.definition.panel_id)

    def _toggle_maximize(self, _event=None) -> None:
        """Toggle maximized mode from the header."""
        self._drag_origin = None
        self._on_toggle_maximize(self.definition.panel_id)

    def _start_resize(self, event, direction: str = "se") -> None:
        """Start resizing a panel."""
        if self._layout_mode == "minimized":
            return
        self._on_focus(self.definition.panel_id)
        self.clear_layout_mode()
        self._resize_origin = (event.x_root, event.y_root, self.geometry_snapshot(), direction)

    def _resize_to(self, event) -> None:
        """Resize the panel with the pointer."""
        if self._resize_origin is None:
            return
        root_x, root_y, start_geometry, direction = self._resize_origin
        surface_w, surface_h = _surface_dimensions(self.master)
        geometry = _resize_geometry(
            direction,
            start_geometry=start_geometry,
            delta_x=event.x_root - root_x,
            delta_y=event.y_root - root_y,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.apply_geometry(geometry)

    def _stop_resize(self, _event=None) -> None:
        """Finish resizing and snap dimensions."""
        if self._resize_origin is None:
            return
        self._resize_origin = None
        surface_w, surface_h = _surface_dimensions(self.master)
        geometry = _constrain_panel_geometry(
            _snap(self.geometry_snapshot()["x"]),
            _snap(self.geometry_snapshot()["y"]),
            _snap(self.geometry_snapshot()["width"]),
            _snap(self.geometry_snapshot()["height"]),
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=self.MIN_WIDTH,
            min_height=self.MIN_HEIGHT,
        )
        self.apply_geometry(geometry)
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
        self._refresh_minimized_tray()

    def _schedule_layout_changed(self) -> None:
        """Debounce layout persistence."""
        if self._disposed:
            return
        self._refresh_empty_state()
        self._refresh_minimized_tray()
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
        x, y = self._suggest_position()
        if geometry:
            x = int(geometry.get("x", x))
            y = int(geometry.get("y", y))
            width = int(geometry.get("width", width))
            height = int(geometry.get("height", height))
        panel = GMTablePanel(
            self.surface,
            definition=definition,
            width=width,
            height=height,
            on_focus=self.bring_to_front,
            on_close=self.remove_panel,
            on_geometry_changed=lambda _panel_id: self._schedule_layout_changed(),
            on_snap_requested=self.snap_panel,
            on_toggle_maximize=self.toggle_panel_maximize,
            on_window_action=self.handle_window_action,
        )
        panel.apply_geometry({"x": x, "y": y, "width": width, "height": height})
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

    def resize_panel(self, panel_id: str, width: int, height: int) -> None:
        """Resize an existing panel and keep it visible."""
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        self.update_idletasks()
        surface_w, surface_h = _surface_dimensions(self.surface)
        geometry = _constrain_panel_geometry(
            int(panel.geometry_snapshot()["x"]),
            int(panel.geometry_snapshot()["y"]),
            int(width),
            int(height),
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=GMTablePanel.MIN_WIDTH,
            min_height=GMTablePanel.MIN_HEIGHT,
        )
        panel.clear_layout_mode()
        panel.apply_geometry(geometry)
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

    def _suggest_position(self) -> tuple[int, int]:
        """Return a cascading default position for a new panel."""
        index = len(self._panels)
        return 28 + ((index * 28) % 280), 24 + ((index * 24) % 220)

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
        if panel.layout_mode in {"left", "right", "maximize"} and panel.restore_layout():
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
        if mode in {"left", "right"}:
            companion_id = self._find_snap_companion(panel_id)
            if companion_id is not None:
                companion = self._panels.get(companion_id)
                if companion is not None:
                    companion_mode = "right" if mode == "left" else "left"
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
        if panel.layout_mode in {"left", "right"} and panel.restore_layout():
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
            panel.apply_geometry({"x": x, "y": y, "width": width, "height": height})
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
            panel.apply_geometry({"x": x, "y": y, "width": width, "height": height})
        self._apply_focus_state(visible_ids[-1])
        self._schedule_layout_changed()

    def clamp_panels(self) -> None:
        """Keep panels inside a reasonable visible area."""
        self.update_idletasks()
        surface_w, surface_h = _surface_dimensions(self.surface)
        for panel in self._panels.values():
            if panel.layout_mode == "minimized":
                continue
            if panel.layout_mode in {"left", "right", "maximize"}:
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
            geometry = panel.geometry_snapshot()
            panel.apply_geometry(
                _constrain_panel_geometry(
                    int(geometry["x"]),
                    int(geometry["y"]),
                    int(geometry["width"]),
                    int(geometry["height"]),
                    surface_w=surface_w,
                    surface_h=surface_h,
                    min_width=GMTablePanel.MIN_WIDTH,
                    min_height=GMTablePanel.MIN_HEIGHT,
                )
            )
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
            snapshot.update(panel.geometry_snapshot())
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
        return {"panels": panels}

    def restore(self, layout: dict[str, object]) -> None:
        """Hydrate panels from a saved layout."""
        self.clear()
        panels = list(layout.get("panels") or [])
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
            geometry = {
                "x": state.get("x", 24),
                "y": state.get("y", 24),
                "width": state.get("width", DEFAULT_PANEL_SIZES.get(definition.kind, DEFAULT_PANEL_SIZES["entity"])[0]),
                "height": state.get("height", DEFAULT_PANEL_SIZES.get(definition.kind, DEFAULT_PANEL_SIZES["entity"])[1]),
            }
            panel = self.add_panel(definition, geometry=geometry)
            restore_geometry = state.get("restore_geometry")
            if isinstance(restore_geometry, dict):
                panel._restore_geometry = {
                    "x": int(restore_geometry.get("x", geometry["x"])),
                    "y": int(restore_geometry.get("y", geometry["y"])),
                    "width": int(restore_geometry.get("width", geometry["width"])),
                    "height": int(restore_geometry.get("height", geometry["height"])),
                }
            layout_mode = str(state.get("layout_mode") or "floating")
            panel._minimized_restore_mode = str(state.get("minimized_restore_mode") or "floating")
            if layout_mode == "minimized":
                panel._layout_mode = "minimized"
                panel.place_forget()
                panel._refresh_window_controls()
            elif layout_mode in {"left", "right", "maximize"}:
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
