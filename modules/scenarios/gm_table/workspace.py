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


def _clamp(value: int, minimum: int, maximum: int) -> int:
    """Clamp a value."""
    return max(minimum, min(maximum, value))


def _snap(value: int, grid: int = 24) -> int:
    """Snap a value to the nearest grid slot."""
    if grid <= 1:
        return value
    return int(round(value / grid) * grid)


@dataclass(slots=True)
class PanelDefinition:
    """Serializable GM Table panel description."""

    panel_id: str
    kind: str
    title: str
    state: dict


class GMTablePanel(ctk.CTkFrame):
    """Floating panel with drag and resize affordances."""

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
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._resize_origin: tuple[int, int, int, int] | None = None
        self._is_focused = False
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self, fg_color=TABLE_PALETTE["panel_alt"], corner_radius=18)
        self.header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self.header.grid_columnconfigure(1, weight=1)

        eyebrow = ctk.CTkLabel(
            self.header,
            text=(definition.kind or "panel").replace("_", " ").title(),
            text_color=TABLE_PALETTE["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        eyebrow.grid(row=0, column=0, padx=(14, 8), pady=(10, 0), sticky="w")

        self.title_label = ctk.CTkLabel(
            self.header,
            text=definition.title,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=17, weight="bold"),
            anchor="w",
        )
        self.title_label.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew")

        close_button = ctk.CTkButton(
            self.header,
            text="x",
            width=30,
            height=28,
            fg_color=TABLE_PALETTE["accent_soft"],
            hover_color="#5B3414",
            text_color=TABLE_PALETTE["text"],
            corner_radius=12,
            command=lambda: self._on_close(self.definition.panel_id),
        )
        close_button.grid(row=0, column=2, rowspan=2, padx=(8, 10), pady=10, sticky="e")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self.resize_handle = ctk.CTkButton(
            self,
            text="//",
            width=32,
            height=24,
            fg_color="transparent",
            hover_color=TABLE_PALETTE["table_chip"],
            text_color=TABLE_PALETTE["muted"],
            corner_radius=10,
        )
        self.resize_handle.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

        self._bind_focus(self)
        self._bind_focus(self.header)
        self._bind_focus(self.body)
        self._install_drag_bindings()
        self._install_resize_bindings()

    def _bind_focus(self, widget) -> None:
        """Raise the panel when clicked."""
        for sequence in ("<Button-1>", "<ButtonPress-1>"):
            widget.bind(sequence, lambda _event: self._on_focus(self.definition.panel_id), add="+")

    def _install_drag_bindings(self) -> None:
        """Enable drag interactions from the header."""
        self.header.bind("<ButtonPress-1>", self._start_drag, add="+")
        self.header.bind("<B1-Motion>", self._drag_to, add="+")
        self.header.bind("<ButtonRelease-1>", self._stop_drag, add="+")
        self.title_label.bind("<ButtonPress-1>", self._start_drag, add="+")
        self.title_label.bind("<B1-Motion>", self._drag_to, add="+")
        self.title_label.bind("<ButtonRelease-1>", self._stop_drag, add="+")

    def _install_resize_bindings(self) -> None:
        """Enable drag-resize interactions."""
        self.resize_handle.bind("<ButtonPress-1>", self._start_resize, add="+")
        self.resize_handle.bind("<B1-Motion>", self._resize_to, add="+")
        self.resize_handle.bind("<ButtonRelease-1>", self._stop_resize, add="+")

    def _start_drag(self, event) -> None:
        """Start moving a panel."""
        self._on_focus(self.definition.panel_id)
        self._drag_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def _drag_to(self, event) -> None:
        """Move the panel with the pointer."""
        if self._drag_origin is None:
            return
        root_x, root_y, start_x, start_y = self._drag_origin
        self.place_configure(x=start_x + (event.x_root - root_x), y=start_y + (event.y_root - root_y))

    def _stop_drag(self, _event=None) -> None:
        """Stop dragging and snap to the workspace grid."""
        if self._drag_origin is None:
            return
        self._drag_origin = None
        self.place_configure(x=_snap(self.winfo_x()), y=_snap(self.winfo_y()))
        self._on_geometry_changed(self.definition.panel_id)

    def _start_resize(self, event) -> None:
        """Start resizing a panel."""
        self._on_focus(self.definition.panel_id)
        self._resize_origin = (event.x_root, event.y_root, self.winfo_width(), self.winfo_height())

    def _resize_to(self, event) -> None:
        """Resize the panel with the pointer."""
        if self._resize_origin is None:
            return
        root_x, root_y, start_w, start_h = self._resize_origin
        new_width = max(self.MIN_WIDTH, start_w + (event.x_root - root_x))
        new_height = max(self.MIN_HEIGHT, start_h + (event.y_root - root_y))
        self._set_size(new_width, new_height)

    def _stop_resize(self, _event=None) -> None:
        """Finish resizing and snap dimensions."""
        if self._resize_origin is None:
            return
        self._resize_origin = None
        self._set_size(_snap(self.winfo_width()), _snap(self.winfo_height()))
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
        """Return the current panel geometry."""
        return {
            "x": int(self.winfo_x()),
            "y": int(self.winfo_y()),
            "width": int(self.winfo_width()),
            "height": int(self.winfo_height()),
        }

    def _set_size(self, width: int, height: int) -> None:
        """Update the CTk widget size using configure, not place geometry."""
        self.configure(width=max(self.MIN_WIDTH, int(width)), height=max(self.MIN_HEIGHT, int(height)))


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
        self.surface.grid(row=0, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.surface.bind("<Configure>", self._refresh_empty_state, add="+")

        self._empty_state = ctk.CTkLabel(
            self.surface,
            text="Use + Add Panel to start building the table.",
            text_color=TABLE_PALETTE["muted"],
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self._empty_state.place(relx=0.5, rely=0.5, anchor="center")

    def _schedule_layout_changed(self) -> None:
        """Debounce layout persistence."""
        if self._disposed:
            return
        self._refresh_empty_state()
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

    def bring_to_front(self, panel_id: str) -> None:
        """Focus a panel and raise it visually."""
        if panel_id not in self._panels:
            return
        for current_id, panel in self._panels.items():
            panel.set_focus_state(current_id == panel_id)
        panel = self._panels[panel_id]
        panel.lift()
        panel.definition.state["z"] = len(self._z_order) + 1
        self._z_order = [value for value in self._z_order if value != panel_id] + [panel_id]
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
        )
        panel._set_size(width, height)
        panel.place(x=x, y=y)
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
        """Grid widget payloads that are returned directly by panel builders."""
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

    def resize_panel(self, panel_id: str, width: int, height: int) -> None:
        """Resize an existing panel and keep it visible."""
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        self.update_idletasks()
        surface_w = max(960, int(self.surface.winfo_width()))
        surface_h = max(640, int(self.surface.winfo_height()))
        new_width = _clamp(int(width), GMTablePanel.MIN_WIDTH, max(GMTablePanel.MIN_WIDTH, surface_w - 24))
        new_height = _clamp(int(height), GMTablePanel.MIN_HEIGHT, max(GMTablePanel.MIN_HEIGHT, surface_h - 24))
        x = _clamp(int(panel.winfo_x()), 12, max(12, surface_w - new_width - 12))
        y = _clamp(int(panel.winfo_y()), 12, max(12, surface_h - new_height - 12))
        panel._set_size(new_width, new_height)
        panel.place_configure(x=x, y=y)
        self.bring_to_front(panel_id)
        self._schedule_layout_changed()

    def ensure_panel_minimum_size(self, panel_id: str, width: int, height: int) -> None:
        """Grow a panel only when it is below a readable minimum size."""
        panel = self._panels.get(panel_id)
        if panel is None:
            return
        current_width = max(GMTablePanel.MIN_WIDTH, int(panel.winfo_width()))
        current_height = max(GMTablePanel.MIN_HEIGHT, int(panel.winfo_height()))
        target_width = max(current_width, int(width))
        target_height = max(current_height, int(height))
        if target_width == current_width and target_height == current_height:
            return
        self.resize_panel(panel_id, target_width, target_height)

    def _suggest_position(self) -> tuple[int, int]:
        """Return a cascading default position for a new panel."""
        index = len(self._panels)
        return 28 + ((index * 28) % 280), 24 + ((index * 24) % 220)

    def auto_arrange(self) -> None:
        """Tile panels across the surface."""
        if not self._panels:
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
        for panel_id in list(self._z_order):
            panel = self._panels.get(panel_id)
            definition = self._definitions.get(panel_id)
            if panel is None:
                continue
            preferred_width, preferred_height = resolve_default_panel_size(
                definition.kind if definition is not None else "entity",
                definition.state if definition is not None else None,
            )
            width = _clamp(
                max(int(panel.winfo_width()), int(preferred_width)),
                GMTablePanel.MIN_WIDTH,
                max_width,
            )
            height = _clamp(
                max(int(panel.winfo_height()), int(preferred_height)),
                GMTablePanel.MIN_HEIGHT,
                max_height,
            )
            if x > margin and (x + width) > (surface_w - margin):
                x = margin
                y += row_height + gutter
                row_height = 0
            panel._set_size(width, height)
            panel.place_configure(x=x, y=y)
            row_height = max(row_height, height)
            x += width + gutter
        self._schedule_layout_changed()

    def clamp_panels(self) -> None:
        """Keep panels inside a reasonable visible area."""
        self.update_idletasks()
        surface_w = max(640, int(self.surface.winfo_width()))
        surface_h = max(420, int(self.surface.winfo_height()))
        for panel in self._panels.values():
            width = _clamp(int(panel.winfo_width()), GMTablePanel.MIN_WIDTH, max(GMTablePanel.MIN_WIDTH, surface_w - 12))
            height = _clamp(int(panel.winfo_height()), GMTablePanel.MIN_HEIGHT, max(GMTablePanel.MIN_HEIGHT, surface_h - 12))
            x = _clamp(int(panel.winfo_x()), 12, max(12, surface_w - width - 12))
            y = _clamp(int(panel.winfo_y()), 12, max(12, surface_h - height - 12))
            panel._set_size(width, height)
            panel.place_configure(x=x, y=y)
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
                state=state,
            )
            if not definition.panel_id:
                continue
            geometry = {
                "x": state.get("x", 24),
                "y": state.get("y", 24),
                "width": state.get("width", DEFAULT_PANEL_SIZES.get(definition.kind, DEFAULT_PANEL_SIZES["entity"])[0]),
                "height": state.get("height", DEFAULT_PANEL_SIZES.get(definition.kind, DEFAULT_PANEL_SIZES["entity"])[1]),
            }
            self.add_panel(definition, geometry=geometry)
        self.clamp_panels()
