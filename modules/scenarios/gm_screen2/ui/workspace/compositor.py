"""Workspace compositor that rebuilds split nodes recursively."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from modules.scenarios.gm_screen2.state.layout_state import LayoutNode, SplitNode, ZoneNode
from modules.scenarios.gm_screen2.ui.workspace.panel_host import PanelHostFrame


class WorkspaceCompositor:
    """Rebuild workspace widgets from a layout tree."""

    def __init__(self, root_frame: ctk.CTkFrame, on_resize_split, on_activate_panel):
        self._root = root_frame
        self._on_resize_split = on_resize_split
        self._on_activate_panel = on_activate_panel
        self.zone_hosts: dict[str, PanelHostFrame] = {}

    def rebuild(self, root_node: LayoutNode, panel_widgets: dict[str, ctk.CTkFrame], visibility: dict[str, bool]) -> None:
        for child in self._root.winfo_children():
            child.destroy()
        self.zone_hosts.clear()
        built = self._build_node(self._root, root_node, panel_widgets, visibility)
        built.pack(fill="both", expand=True)

    def _build_node(self, parent, node: LayoutNode, panel_widgets: dict[str, ctk.CTkFrame], visibility: dict[str, bool]):
        if isinstance(node, ZoneNode):
            host = PanelHostFrame(parent, on_activate=lambda panel_id: self._on_activate_panel(node.id, panel_id))
            host.unmount_all()
            for panel_id in node.panel_stack:
                widget = panel_widgets.get(panel_id)
                if widget is None or not visibility.get(panel_id, True):
                    continue
                host.mount(panel_id, widget, active=(panel_id == node.active_panel_id))
            self.zone_hosts[node.id] = host
            return host

        orient = tk.HORIZONTAL if node.axis == "horizontal" else tk.VERTICAL
        paned = tk.PanedWindow(parent, orient=orient, sashrelief=tk.RAISED, bd=0)
        first = self._build_node(paned, node.first, panel_widgets, visibility)
        second = self._build_node(paned, node.second, panel_widgets, visibility)
        paned.add(first, stretch="always")
        paned.add(second, stretch="always")
        paned.bind("<ButtonRelease-1>", lambda _event, split_id=node.id: self._on_resize_split(split_id, _ratio_from_sash(paned)))
        return paned


def _ratio_from_sash(paned: tk.PanedWindow) -> float:
    try:
        x, y = paned.sash_coord(0)
        total = max(1, paned.winfo_width() if str(paned.cget("orient")) == "horizontal" else paned.winfo_height())
        return max(0.1, min(0.9, (x if str(paned.cget("orient")) == "horizontal" else y) / total))
    except Exception:
        return 0.5
