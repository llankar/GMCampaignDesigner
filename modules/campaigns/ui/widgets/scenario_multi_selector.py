from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class ScenarioMultiSelector(ctk.CTkFrame):
    """Searchable multi-select list used to link scenarios to a campaign arc."""

    def __init__(self, master, scenarios: list[str], *, label: str = "Scenarios"):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=label).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search scenarios...")
        self.search_entry.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, exportselection=False, height=8)
        self.listbox.grid(row=2, column=0, sticky="ew")

        self._all_scenarios = list(scenarios or [])
        self._visible_scenarios: list[str] = []
        self._selected_scenarios: set[str] = set()
        self._refresh_list()

    def set_values(self, values: list[str]):
        self._selected_scenarios = {
            str(value).strip() for value in (values or []) if str(value).strip()
        }
        self._apply_selection()

    def get_values(self) -> list[str]:
        self._capture_current_selection()
        return [name for name in self._all_scenarios if name in self._selected_scenarios]

    def _on_search(self, _event=None):
        self._capture_current_selection()
        self._refresh_list(query=self.search_var.get().strip())

    def _capture_current_selection(self):
        visible_set = set(self._visible_scenarios)
        self._selected_scenarios.difference_update(visible_set)
        for index in self.listbox.curselection():
            if 0 <= index < len(self._visible_scenarios):
                self._selected_scenarios.add(self._visible_scenarios[index])

    def _refresh_list(self, query: str = ""):
        lowered = query.lower()
        if lowered:
            self._visible_scenarios = [
                scenario for scenario in self._all_scenarios if lowered in scenario.lower()
            ]
        else:
            self._visible_scenarios = list(self._all_scenarios)

        self.listbox.delete(0, tk.END)
        for scenario in self._visible_scenarios:
            self.listbox.insert(tk.END, scenario)
        self._apply_selection()

    def _apply_selection(self):
        self.listbox.selection_clear(0, tk.END)
        for index, scenario in enumerate(self._visible_scenarios):
            if scenario in self._selected_scenarios:
                self.listbox.selection_set(index)
