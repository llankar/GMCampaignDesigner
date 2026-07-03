"""Viewport-fixed fixed table overlay widgets."""

from __future__ import annotations
import tkinter as tk
from types import SimpleNamespace
import customtkinter as ctk

from modules.helpers import theme_manager

from .models import FixedOverlayItem, FixedOverlayState
from .style import (
    OVERLAY_OPACITY,
    OVERLAY_OPACITY_OPTIONS,
    blend_hex_color,
    label_to_opacity,
    normalize_overlay_opacity,
    opacity_to_label,
)
from .theme import get_fixed_overlay_palette
from .overlay_window import TransparentOverlayWindow

TAB_WIDTH = 28
COLLAPSED_TAB_TEXT = "›"
EXPANDED_TAB_TEXT = "‹"
MIN_OVERLAY_WIDTH = 300
MAX_OVERLAY_WIDTH = 1100
EMPTY_OVERLAY_WIDTH = 300
DEFAULT_ITEM_WIDTH = 340
DEFAULT_ITEM_HEIGHT = 260
MIN_ITEM_WIDTH = 240
MIN_ITEM_HEIGHT = 140
ITEM_CHROME_WIDTH = 48


class FixedOverlayView:
    """Collapsible viewport overlay anchored to the left edge of the GM Table."""

    def __init__(
        self, master, *, panel_builder, on_changed=None, on_add_requested=None
    ):
        self._palette = get_fixed_overlay_palette()
        self._state = FixedOverlayState()
        self._overlay_layer = TransparentOverlayWindow(
            master,
            background=self._overlay_surface_color(),
            opacity=self._state.opacity,
        )
        self._shell = self._overlay_layer.shell
        self._shell.configure(border_color=self._palette["panel_focus"])
        self._panel_builder = panel_builder
        self._on_changed = on_changed
        self._on_add_requested = on_add_requested
        self._payloads: dict[str, object] = {}
        self._item_frames: dict[str, tk.Widget] = {}
        self._item_bodies: dict[str, tk.Widget] = {}
        self._theme_unsub = theme_manager.register_theme_change_listener(
            self._on_theme_changed
        )
        self._resize_start_x = 0
        self._resize_start_width = 0
        self._item_resize_context: dict[str, int] | None = None
        self._build_shell()
        self.apply_state(self._state)

    def _overlay_surface_color(self) -> str:
        """Return the fixed overlay surface color at the selected opacity."""
        return blend_hex_color(
            self._palette["panel_bg"],
            self._palette["table_bg"],
            self._current_opacity(),
        )

    def _overlay_item_color(self) -> str:
        """Return fixed item chrome at the selected opacity."""
        return blend_hex_color(
            self._palette["panel_alt"],
            self._palette["table_bg"],
            self._current_opacity(),
        )

    def _current_opacity(self) -> float:
        return normalize_overlay_opacity(getattr(self._state, "opacity", OVERLAY_OPACITY))

    def _build_shell(self) -> None:
        host = getattr(self, "_shell", self)
        host.grid_columnconfigure(0, weight=1)
        host.grid_columnconfigure(1, weight=0)
        host.grid_columnconfigure(2, weight=0)
        host.grid_rowconfigure(0, weight=1)
        self.content = ctk.CTkFrame(
            host, fg_color=self._overlay_surface_color(), corner_radius=0
        )
        self.content.grid(row=0, column=0, sticky="nsew")
        self.resize_handle = ctk.CTkFrame(
            host,
            width=8,
            fg_color=self._palette["panel_focus"],
            cursor="sb_h_double_arrow",
        )
        self.resize_handle.grid(row=0, column=1, sticky="ns")
        self.tab_button = ctk.CTkButton(
            host,
            text=EXPANDED_TAB_TEXT,
            width=TAB_WIDTH,
            corner_radius=0,
            fg_color=self._palette["accent"],
            hover_color=self._palette["accent_hover"],
            text_color=self._palette["button_text_on_accent"],
            command=self.toggle_collapsed,
        )
        self.tab_button.grid(row=0, column=2, sticky="ns")
        self.resize_handle.bind("<ButtonPress-1>", self._start_resize, add="+")
        self.resize_handle.bind("<B1-Motion>", self._drag_resize, add="+")
        self.resize_handle.bind("<ButtonRelease-1>", self._finish_resize, add="+")
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.header = ctk.CTkFrame(
            self.content, fg_color=self._overlay_surface_color(), corner_radius=0
        )
        header = self.header
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Fixed Table",
            text_color=self._palette["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.opacity_menu = ctk.CTkOptionMenu(
            header,
            values=[opacity_to_label(value) for value in OVERLAY_OPACITY_OPTIONS],
            width=82,
            command=self._handle_opacity_selected,
        )
        self.opacity_menu.grid(row=0, column=1, padx=(0, 6), pady=6)
        self.add_button = ctk.CTkButton(
            header, text="+ Add", width=68, command=self._request_add
        )
        self.add_button.grid(row=0, column=2, padx=(0, 6), pady=6)
        ctk.CTkButton(header, text="‹", width=32, command=self.collapse).grid(
            row=0, column=3, padx=(0, 8), pady=6
        )
        self.items_host = ctk.CTkScrollableFrame(
            self.content, fg_color=self._overlay_surface_color()
        )
        self.items_host.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.empty_label = ctk.CTkLabel(
            self.items_host,
            text="Pinned Table is empty. Use Add to Fixed Table.",
            text_color=self._palette["muted"],
            wraplength=300,
        )
        self.empty_label.pack(fill="x", padx=8, pady=12)

    def _on_theme_changed(self, theme: str) -> None:
        """Refresh fixed-overlay chrome colors after the global theme changes."""
        self._palette = get_fixed_overlay_palette(theme)
        self._refresh_overlay_colors()
        self.resize_handle.configure(fg_color=self._palette["panel_focus"])
        self.tab_button.configure(
            fg_color=self._palette["accent"],
            hover_color=self._palette["accent_hover"],
            text_color=self._palette["button_text_on_accent"],
        )
        self._refresh_items()

    def destroy(self) -> None:
        """Release the theme listener before destroying the overlay."""
        if self._theme_unsub is not None:
            self._theme_unsub()
            self._theme_unsub = None
        self._overlay_layer.destroy()

    def configure(self, **kwargs: object) -> None:
        self._overlay_layer.configure(**kwargs)

    def place_configure(self, **kwargs: object) -> None:
        self._overlay_layer.place_configure(**kwargs)

    def place(self, **kwargs: object) -> None:
        self._overlay_layer.place(**kwargs)

    def place_forget(self) -> None:
        self._overlay_layer.place_forget()

    def show(self) -> bool:
        return self._overlay_layer.show()

    def hide(self) -> None:
        self._overlay_layer.hide()

    def sync_to_anchor(self) -> bool:
        return self._overlay_layer.sync_to_anchor()

    def ensure_visible(self) -> bool:
        return self._overlay_layer.ensure_visible()

    def is_geometry_ready(self) -> bool:
        return self._overlay_layer.is_geometry_ready()

    def lift(self) -> None:
        self._overlay_layer.lift()

    def update_idletasks(self) -> None:
        self._overlay_layer.update_idletasks()

    @property
    def transparency_support(self):
        return self._overlay_layer.support

    def apply_state(self, state: FixedOverlayState) -> None:
        self._state = state
        self._state.opacity = self._current_opacity()
        self._sync_opacity_control()
        self._set_overlay_layer_opacity(self._state.opacity)
        self._refresh_overlay_colors()
        self._refresh_items()
        self._refresh_geometry()

    def _sync_opacity_control(self) -> None:
        opacity_menu = getattr(self, "opacity_menu", None)
        if hasattr(opacity_menu, "set"):
            opacity_menu.set(opacity_to_label(self._current_opacity()))

    def _refresh_overlay_colors(self) -> None:
        surface_color = self._overlay_surface_color()
        item_color = self._overlay_item_color()
        self.configure(
            fg_color=surface_color,
            border_color=self._palette["panel_focus"],
        )
        self.content.configure(fg_color=surface_color)
        self.header.configure(fg_color=surface_color)
        self.items_host.configure(fg_color=surface_color)
        for frame in self._item_frames.values():
            try:
                frame.configure(fg_color=item_color)
            except Exception:
                pass

    def _handle_opacity_selected(self, label: str) -> None:
        opacity = label_to_opacity(label)
        if opacity == self._current_opacity():
            self._sync_opacity_control()
            return
        self._state.opacity = opacity
        self._sync_opacity_control()
        self._set_overlay_layer_opacity(opacity)
        self._refresh_overlay_colors()
        self._changed()

    def _set_overlay_layer_opacity(self, opacity: float) -> None:
        set_opacity = getattr(self._overlay_layer, "set_opacity", None)
        if callable(set_opacity):
            set_opacity(opacity)

    def refresh_geometry_without_lift(self) -> None:
        """Refresh placement without changing global window stacking order."""
        self._refresh_geometry(lift_overlay=False)

    def _refresh_geometry(self, *, lift_overlay: bool = True) -> None:
        if not self._state.visible:
            hide = getattr(self, "hide", None)
            if callable(hide):
                hide()
            else:
                self.place_forget()
            return

        width = (
            TAB_WIDTH
            if self._state.collapsed
            else FixedOverlayView._preferred_overlay_width(self)
        )

        if self._state.collapsed:
            self.content.grid_remove()
            self.resize_handle.grid_remove()
            # When the overlay is narrowed to TAB_WIDTH, keep the expand handle
            # in the first visible grid column. Leaving it in column 2 can push
            # the button outside the clipped toplevel on some Tk/window-manager
            # combinations, which makes the collapsed overlay look like it has
            # no way to expand.
            self.tab_button.grid(row=0, column=0, sticky="ns")
            self.tab_button.configure(text=COLLAPSED_TAB_TEXT)
        else:
            self.content.grid(row=0, column=0, sticky="nsew")
            self.resize_handle.grid(row=0, column=1, sticky="ns")
            self.tab_button.grid(row=0, column=2, sticky="ns")
            self.tab_button.configure(text=EXPANDED_TAB_TEXT)

        self.configure(width=width)
        if not self._state.collapsed:
            self._state.width = width
        FixedOverlayView._place_with_width(self, width)
        show = getattr(self, "show", None)
        if callable(show):
            if not show():
                return
        else:
            ensure_visible = getattr(self, "ensure_visible", None)
            if callable(ensure_visible) and not ensure_visible():
                return
        if lift_overlay:
            self.lift()

    def _place_with_width(self, width: int) -> None:
        """Place the overlay with an explicit width for reliable geometry."""
        options = {
            "x": 0,
            "y": 0,
            "relx": 0,
            "rely": 0,
            "width": width,
            "relwidth": 0,
            "relheight": 1.0,
        }
        place_configure = getattr(self, "place_configure", None)
        if callable(place_configure):
            place_configure(**options)
        else:
            self.place(**options)
        sync_to_anchor = getattr(self, "sync_to_anchor", None)
        if callable(sync_to_anchor):
            sync_to_anchor()

    def _refresh_items(self) -> None:
        for child in list(self.items_host.winfo_children()):
            child.destroy()
        self._payloads.clear()
        self._item_frames.clear()
        self._item_bodies.clear()
        if not self._state.items:
            self.empty_label = ctk.CTkLabel(
                self.items_host,
                text="Pinned Table is empty. Use Add to Fixed Table.",
                text_color=self._palette["muted"],
                wraplength=300,
            )
            self.empty_label.pack(fill="x", padx=8, pady=12)
            return
        for item in self._state.items:
            item_width, item_height = self._item_dimensions(item)
            frame = ctk.CTkFrame(
                self.items_host,
                fg_color=self._overlay_item_color(),
                border_width=1,
                border_color=self._palette["panel_border"],
                corner_radius=12,
                width=item_width,
                height=item_height,
            )
            frame.pack(fill="none", expand=False, padx=4, pady=6, anchor="nw")
            frame.grid_propagate(False)
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=0)
            frame.grid_rowconfigure(1, weight=1)
            self._item_frames[item.item_id] = frame

            header = ctk.CTkFrame(frame, fg_color="transparent")
            header.grid(
                row=0, column=0, sticky="ew", padx=10, pady=(8, 4), columnspan=2
            )
            header.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                header,
                text=item.title,
                text_color=self._palette["text"],
                font=ctk.CTkFont(weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            actions = ctk.CTkFrame(header, fg_color="transparent")
            actions.grid(row=0, column=1, sticky="e", padx=(8, 0))
            ctk.CTkButton(
                actions,
                text="Remove",
                width=72,
                fg_color=self._palette["danger"],
                hover_color=self._palette["danger_hover"],
                text_color=self._palette["button_text_on_accent"],
                command=lambda item_id=item.item_id: self._remove_item(item_id),
            ).grid(row=0, column=0, sticky="e")

            body = ctk.CTkFrame(frame, fg_color="transparent")
            body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8), columnspan=2)
            body.grid_rowconfigure(0, weight=1)
            body.grid_columnconfigure(0, weight=1)
            self._item_bodies[item.item_id] = body
            resize_handle = ctk.CTkLabel(
                frame,
                text="↘",
                width=22,
                height=22,
                cursor="bottom_right_corner",
                text_color=self._palette["muted"],
                fg_color=self._palette["table_chip"],
                corner_radius=8,
            )
            resize_handle.grid(row=2, column=1, sticky="se", padx=(0, 8), pady=(0, 8))
            resize_handle.bind(
                "<ButtonPress-1>",
                lambda event, item_id=item.item_id: self._start_item_resize(
                    event, item_id
                ),
                add="+",
            )
            resize_handle.bind(
                "<B1-Motion>",
                lambda event, item_id=item.item_id: self._drag_item_resize(
                    event, item_id
                ),
                add="+",
            )
            resize_handle.bind("<ButtonRelease-1>", self._finish_item_resize, add="+")

            payload = self._panel_builder(
                body,
                SimpleNamespace(
                    panel_id=item.item_id,
                    kind=item.kind,
                    title=item.title,
                    state=item.state,
                ),
            )
            self._mount_payload_widget(body, payload)
            self._payloads[item.item_id] = payload

    def _remove_item(self, item_id: str) -> None:
        before_count = len(self._state.items)
        self._state.items = [
            item for item in self._state.items if item.item_id != item_id
        ]
        if len(self._state.items) == before_count:
            return
        self._payloads.pop(item_id, None)
        self._refresh_items()
        self._changed()

    @staticmethod
    def _mount_payload_widget(host: ctk.CTkFrame, payload: object) -> None:
        """Grid directly-returned widgets so fixed-table items render like panels."""
        if not isinstance(payload, tk.Widget):
            return
        try:
            if payload.master is not host or payload.winfo_manager():
                return
            payload.grid(row=0, column=0, sticky="nsew")
        except Exception:
            return

    def _preferred_overlay_width(self) -> int:
        if not self._state.items:
            return EMPTY_OVERLAY_WIDTH
        item_widths = [
            FixedOverlayView._item_dimensions(item)[0] + ITEM_CHROME_WIDTH
            for item in self._state.items
        ]
        preferred = max([int(self._state.width or 360), *item_widths] or [360])
        return max(MIN_OVERLAY_WIDTH, min(MAX_OVERLAY_WIDTH, preferred))

    @staticmethod
    def _item_dimensions(item: FixedOverlayItem) -> tuple[int, int]:
        state = item.state if isinstance(item.state, dict) else {}
        width = int(state.get("fixed_overlay_width") or DEFAULT_ITEM_WIDTH)
        height = int(state.get("fixed_overlay_height") or DEFAULT_ITEM_HEIGHT)
        return max(
            MIN_ITEM_WIDTH, min(MAX_OVERLAY_WIDTH - ITEM_CHROME_WIDTH, width)
        ), max(MIN_ITEM_HEIGHT, height)

    def _find_item(self, item_id: str) -> FixedOverlayItem | None:
        return next(
            (item for item in self._state.items if item.item_id == item_id), None
        )

    def _start_item_resize(self, event, item_id: str) -> str:
        item = self._find_item(item_id)
        if item is None:
            return "break"
        width, height = self._item_dimensions(item)
        self._item_resize_context = {
            "item_id": item_id,
            "x": int(event.x_root),
            "y": int(event.y_root),
            "width": width,
            "height": height,
        }
        return "break"

    def _drag_item_resize(self, event, item_id: str) -> str:
        context = self._item_resize_context
        if not context or context.get("item_id") != item_id:
            return "break"
        item = self._find_item(item_id)
        if item is None:
            return "break"
        delta_x = int(event.x_root) - int(context["x"])
        delta_y = int(event.y_root) - int(context["y"])
        new_width = max(
            MIN_ITEM_WIDTH,
            min(MAX_OVERLAY_WIDTH - ITEM_CHROME_WIDTH, int(context["width"]) + delta_x),
        )
        new_height = max(MIN_ITEM_HEIGHT, int(context["height"]) + delta_y)
        item.state["fixed_overlay_width"] = new_width
        item.state["fixed_overlay_height"] = new_height
        self._resize_item_widgets(item.item_id, new_width, new_height)
        self._refresh_geometry()
        return "break"

    def _resize_item_widgets(self, item_id: str, width: int, height: int) -> None:
        """Resize the item shell and its payload host without rebuilding content."""
        item_frame = self._item_frames.get(item_id)
        if isinstance(item_frame, tk.Widget):
            item_frame.configure(width=width, height=height)
            try:
                item_frame.pack_configure(fill="none", expand=False)
            except Exception:
                pass
        body = self._item_bodies.get(item_id)
        if isinstance(body, tk.Widget):
            body.configure(
                width=max(MIN_ITEM_WIDTH, width - 16), height=max(1, height - 76)
            )
        payload = self._payloads.get(item_id)
        if isinstance(payload, tk.Widget):
            try:
                payload.configure(
                    width=max(MIN_ITEM_WIDTH, width - 16), height=max(1, height - 76)
                )
            except Exception:
                pass
        try:
            self.update_idletasks()
        except Exception:
            pass

    def _finish_item_resize(self, _event) -> str:
        self._item_resize_context = None
        self._changed()
        return "break"

    def _start_resize(self, event) -> str:
        self._resize_start_x = int(event.x_root)
        self._resize_start_width = int(self._state.width)
        return "break"

    def _drag_resize(self, event) -> str:
        delta = int(event.x_root) - self._resize_start_x
        self._state.width = max(
            MIN_OVERLAY_WIDTH, min(MAX_OVERLAY_WIDTH, self._resize_start_width + delta)
        )
        self._refresh_geometry()
        return "break"

    def _finish_resize(self, _event) -> str:
        self._changed()
        return "break"

    def expand(self) -> None:
        self._state.collapsed = False
        self._refresh_geometry()
        self._changed()

    def collapse(self) -> None:
        self._state.collapsed = True
        self._refresh_geometry()
        self._changed()

    def toggle_collapsed(self) -> None:
        self.expand() if self._state.collapsed else self.collapse()

    def add_item(self, item: FixedOverlayItem) -> None:
        self._state.items.append(item)
        self._state.collapsed = False
        self._refresh_items()
        self._refresh_geometry()
        self._changed()

    def get_state(self) -> dict:
        # collect per-item viewer state
        for item in self._state.items:
            payload = self._payloads.get(item.item_id)
            if hasattr(payload, "get_state"):
                try:
                    dynamic = payload.get_state() or {}
                    if isinstance(dynamic, dict):
                        item.state.update(dynamic)
                except Exception:
                    pass
        return self._state.to_dict()

    @property
    def collapsed(self) -> bool:
        return self._state.collapsed

    def _request_add(self) -> None:
        """Ask the owning GM Table view to show fixed-overlay add actions."""
        if callable(self._on_add_requested):
            self._on_add_requested(self.add_button)

    def _changed(self) -> None:
        if callable(self._on_changed):
            self._on_changed()
