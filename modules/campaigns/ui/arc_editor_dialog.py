from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from modules.campaigns.ui.widgets import ScenarioMultiSelector


class ArcEditorDialog(ctk.CTkToplevel):
    """Modal dialog used by campaign wizard to create/update one campaign arc."""

    def __init__(self, master, scenarios: list[str], initial_data: dict | None = None):
        super().__init__(master)
        self.title("Campaign Arc")
        self.geometry("700x560")
        self.result = None

        initial = initial_data or {}

        self.name_var = ctk.StringVar(value=initial.get("name", ""))
        self.status_var = ctk.StringVar(value=initial.get("status", "Planned"))

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(container, text="Arc Name").pack(anchor="w")
        ctk.CTkEntry(container, textvariable=self.name_var).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(container, text="Summary").pack(anchor="w")
        self.summary_box = ctk.CTkTextbox(container, height=90)
        self.summary_box.pack(fill="x", pady=(0, 8))
        self.summary_box.insert("1.0", initial.get("summary", ""))

        ctk.CTkLabel(container, text="Objective").pack(anchor="w")
        self.objective_box = ctk.CTkTextbox(container, height=90)
        self.objective_box.pack(fill="x", pady=(0, 8))
        self.objective_box.insert("1.0", initial.get("objective", ""))

        ctk.CTkLabel(container, text="Status").pack(anchor="w")
        ctk.CTkOptionMenu(container, variable=self.status_var, values=["Planned", "Running", "Done", "Paused"]).pack(fill="x", pady=(0, 8))

        self.scenario_selector = ScenarioMultiSelector(
            container,
            scenarios,
            label="Linked Scenarios",
        )
        self.scenario_selector.pack(fill="x")

        initial_scenarios = initial.get("scenarios") or []
        if not initial_scenarios and scenarios:
            initial_scenarios = scenarios[:2]
        self.scenario_selector.set_values(initial_scenarios)

        if scenarios:
            ctk.CTkLabel(
                container,
                text=f"Available scenarios: {', '.join(scenarios[:12])}{'…' if len(scenarios) > 12 else ''}",
                wraplength=660,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))

        btns = ctk.CTkFrame(container, fg_color="transparent")
        btns.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Save Arc", command=self._save).pack(side="right", padx=4)

        self.transient(master)
        self.grab_set()
        self.focus_force()

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Arc name is required.", parent=self)
            return

        scenarios = self.scenario_selector.get_values()

        self.result = {
            "name": name,
            "summary": self.summary_box.get("1.0", "end").strip(),
            "objective": self.objective_box.get("1.0", "end").strip(),
            "status": self.status_var.get().strip() or "Planned",
            "scenarios": scenarios,
        }
        self.destroy()
