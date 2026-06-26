"""Search dialog for jumping between GM Table panels."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from .search_index import build_panel_search_index, filter_panel_search_index


class GMTablePanelSearchDialog(ctk.CTkToplevel):
    """Small modeless panel search window."""

    def __init__(self, master, *, workspace) -> None:
        super().__init__(master)
        self.title("Search GM Table Panels")
        self.transient(master.winfo_toplevel())
        self._workspace = workspace
        self._results = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._query = tk.StringVar()
        ctk.CTkLabel(self, text="Search panels by title, type, or state").grid(row=0, column=0, padx=14, pady=(14, 6), sticky="w")
        entry = ctk.CTkEntry(self, textvariable=self._query, width=420)
        entry.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")
        self._list = tk.Listbox(self, height=10)
        self._list.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self._query.trace_add("write", lambda *_: self._refresh())
        entry.bind("<Return>", lambda _e: self._jump_selected())
        self._list.bind("<Double-Button-1>", lambda _e: self._jump_selected())
        self.bind("<Escape>", lambda _e: self.destroy())
        self._refresh()
        entry.focus_set()

    def _refresh(self) -> None:
        index = build_panel_search_index(self._workspace.list_panels(include_minimized=True))
        self._results = filter_panel_search_index(index, self._query.get())
        self._list.delete(0, "end")
        for result in self._results:
            flags = []
            if result.minimized:
                flags.append("minimized")
            if result.locked:
                flags.append("locked")
            suffix = f" ({', '.join(flags)})" if flags else ""
            self._list.insert("end", f"{result.title} — {result.kind}{suffix}")
        if self._results:
            self._list.selection_set(0)

    def _jump_selected(self) -> None:
        selection = self._list.curselection()
        if not selection:
            return
        result = self._results[int(selection[0])]
        self._workspace.jump_to_panel(result.panel_id)
        self.destroy()
