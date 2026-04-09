"""Panel host widget capable of dynamic mount/unmount."""

from __future__ import annotations

import customtkinter as ctk


class PanelHostFrame(ctk.CTkFrame):
    """Host for one zone panel stack with tab buttons."""

    def __init__(self, master, on_activate, **kwargs):
        super().__init__(master, **kwargs)
        self._on_activate = on_activate
        self._tab_bar = ctk.CTkFrame(self)
        self._tab_bar.pack(fill="x", padx=4, pady=(4, 0))
        self._content = ctk.CTkFrame(self)
        self._content.pack(fill="both", expand=True, padx=4, pady=4)
        self._mounted: dict[str, ctk.CTkFrame] = {}

    def mount(self, panel_id: str, widget: ctk.CTkFrame, active: bool) -> None:
        self._mounted[panel_id] = widget
        button = ctk.CTkButton(self._tab_bar, text=panel_id.replace("_", " ").title(), width=90, height=24, command=lambda: self._on_activate(panel_id))
        button.pack(side="left", padx=2)
        if active:
            widget.pack(in_=self._content, fill="both", expand=True)

    def unmount_all(self) -> None:
        for child in self._tab_bar.winfo_children():
            child.destroy()
        for child in self._content.winfo_children():
            child.pack_forget()
        self._mounted.clear()
