"""Viewport-fixed fixed table overlay widgets."""
from __future__ import annotations
import tkinter as tk
from types import SimpleNamespace
import customtkinter as ctk

TABLE_PALETTE = {
    "table_bg": "#11141E", "table_alt": "#171C29", "table_line": "#2D364B",
    "table_chip": "#20283A", "panel_bg": "#0F1523", "panel_alt": "#171F30",
    "panel_border": "#34405A", "panel_focus": "#7DD3FC", "text": "#F4F7FB",
    "muted": "#9EABC2", "accent": "#F59E0B", "accent_soft": "#453116", "danger": "#F87171",
}
from .models import FixedOverlayItem, FixedOverlayState

TAB_WIDTH = 28


class FixedOverlayView(ctk.CTkFrame):
    """Collapsible viewport overlay anchored to the left edge of the GM Table."""

    def __init__(self, master, *, panel_builder, on_changed=None):
        super().__init__(master, width=TAB_WIDTH, fg_color=TABLE_PALETTE["panel_bg"], corner_radius=0, border_width=1, border_color=TABLE_PALETTE["panel_focus"])
        self._panel_builder = panel_builder
        self._on_changed = on_changed
        self._state = FixedOverlayState()
        self._payloads: dict[str, object] = {}
        self._resize_start_x = 0
        self._resize_start_width = 0
        self._build_shell()
        self.apply_state(self._state)

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)
        self.tab_button = ctk.CTkButton(self, text="›", width=TAB_WIDTH, corner_radius=0, fg_color=TABLE_PALETTE["accent"], hover_color="#D97706", text_color="#111827", command=self.toggle_collapsed)
        self.tab_button.grid(row=0, column=0, sticky="ns")
        self.content = ctk.CTkFrame(self, fg_color=TABLE_PALETTE["panel_bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.resize_handle = ctk.CTkFrame(self, width=8, fg_color=TABLE_PALETTE["panel_focus"], cursor="sb_h_double_arrow")
        self.resize_handle.grid(row=0, column=2, sticky="ns")
        self.resize_handle.bind("<ButtonPress-1>", self._start_resize, add="+")
        self.resize_handle.bind("<B1-Motion>", self._drag_resize, add="+")
        self.resize_handle.bind("<ButtonRelease-1>", self._finish_resize, add="+")
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self.content, fg_color=TABLE_PALETTE["table_alt"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Fixed Table", text_color=TABLE_PALETTE["text"], font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ctk.CTkButton(header, text="‹", width=32, command=self.collapse).grid(row=0, column=1, padx=8, pady=6)
        self.items_host = ctk.CTkScrollableFrame(self.content, fg_color=TABLE_PALETTE["panel_bg"])
        self.items_host.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.empty_label = ctk.CTkLabel(self.items_host, text="Pinned Table is empty. Use Add to Fixed Table.", text_color=TABLE_PALETTE["muted"], wraplength=300)
        self.empty_label.pack(fill="x", padx=8, pady=12)

    def apply_state(self, state: FixedOverlayState) -> None:
        self._state = state
        self._refresh_items()
        self._refresh_geometry()

    def _refresh_geometry(self) -> None:
        if not self._state.visible:
            self.place_forget(); return
        width = TAB_WIDTH if self._state.collapsed else int(self._state.width)
        self.configure(width=width)
        # CustomTkinter requires fixed dimensions to be configured on the
        # widget itself instead of supplied to place().  The place manager only
        # anchors the overlay to the viewport edge and stretches it vertically.
        self.place(x=0, y=0, relheight=1.0)
        if self._state.collapsed:
            self.content.grid_remove(); self.resize_handle.grid_remove(); self.tab_button.configure(text="›")
        else:
            self.content.grid(); self.resize_handle.grid(); self.tab_button.configure(text="‹")
        self.lift()

    def _refresh_items(self) -> None:
        for child in list(self.items_host.winfo_children()):
            child.destroy()
        self._payloads.clear()
        if not self._state.items:
            self.empty_label = ctk.CTkLabel(self.items_host, text="Pinned Table is empty. Use Add to Fixed Table.", text_color=TABLE_PALETTE["muted"], wraplength=300)
            self.empty_label.pack(fill="x", padx=8, pady=12)
            return
        for item in self._state.items:
            frame = ctk.CTkFrame(self.items_host, fg_color=TABLE_PALETTE["panel_alt"], corner_radius=12)
            frame.pack(fill="both", expand=True, padx=4, pady=6)
            frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(frame, text=item.title, text_color=TABLE_PALETTE["text"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
            body = ctk.CTkFrame(frame, fg_color="transparent")
            body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
            body.grid_rowconfigure(0, weight=1)
            body.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(1, weight=1)
            payload = self._panel_builder(body, SimpleNamespace(panel_id=item.item_id, kind=item.kind, title=item.title, state=item.state))
            self._mount_payload_widget(body, payload)
            self._payloads[item.item_id] = payload

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

    def _start_resize(self, event) -> str:
        self._resize_start_x = int(event.x_root)
        self._resize_start_width = int(self._state.width)
        return "break"

    def _drag_resize(self, event) -> str:
        delta = int(event.x_root) - self._resize_start_x
        self._state.width = max(280, min(1100, self._resize_start_width + delta))
        self._refresh_geometry()
        return "break"

    def _finish_resize(self, _event) -> str:
        self._changed()
        return "break"

    def expand(self) -> None:
        self._state.collapsed = False; self._refresh_geometry(); self._changed()
    def collapse(self) -> None:
        self._state.collapsed = True; self._refresh_geometry(); self._changed()
    def toggle_collapsed(self) -> None:
        self.expand() if self._state.collapsed else self.collapse()
    def add_item(self, item: FixedOverlayItem) -> None:
        self._state.items.append(item); self._state.collapsed = False; self._refresh_items(); self._refresh_geometry(); self._changed()
    def get_state(self) -> dict:
        # collect per-item viewer state
        for item in self._state.items:
            payload = self._payloads.get(item.item_id)
            if hasattr(payload, "get_state"):
                try:
                    dynamic = payload.get_state() or {}
                    if isinstance(dynamic, dict): item.state.update(dynamic)
                except Exception: pass
        return self._state.to_dict()
    @property
    def collapsed(self) -> bool: return self._state.collapsed
    def _changed(self) -> None:
        if callable(self._on_changed): self._on_changed()
