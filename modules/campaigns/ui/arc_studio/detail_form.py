from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from modules.campaigns.shared.arc_status import canonicalize_arc_status
from modules.generic.editor.styles import EDITOR_PALETTE, option_menu_style, toolbar_entry_style


class ArcDetailForm(ctk.CTkFrame):
    """Editor for one selected arc."""

    def __init__(self, master, on_change):
        super().__init__(master, fg_color=EDITOR_PALETTE["surface_soft"], corner_radius=12)
        self._on_change = on_change
        self._is_loading = False

        self.name_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Planned")
        self.scenario_entry_var = tk.StringVar()
        self._scenario_items: list[str] = []

        ctk.CTkLabel(self, text="Arc Details", font=("Arial", 16, "bold")).pack(anchor="w", padx=12, pady=(12, 8))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12)
        ctk.CTkLabel(row, text="Name", text_color=EDITOR_PALETTE["text"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="Status", text_color=EDITOR_PALETTE["text"]).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.name_entry = ctk.CTkEntry(row, textvariable=self.name_var, **toolbar_entry_style())
        self.name_entry.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        self.status_menu = ctk.CTkOptionMenu(
            row,
            variable=self.status_var,
            values=["Planned", "In Progress", "Blocked", "Resolved"],
            command=lambda _value: self._notify_change(),
            **option_menu_style(),
        )
        self.status_menu.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(2, 8))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        self.summary_box = self._textbox("Summary")
        self.objective_box = self._textbox("Objective")
        self.thread_box = self._textbox("Thread")
        self._build_scenarios_editor()

        self.validation_label = ctk.CTkLabel(self, text="", text_color=EDITOR_PALETTE["muted_text"], justify="left")
        self.validation_label.pack(anchor="w", padx=12, pady=(4, 12))

        self.name_var.trace_add("write", lambda *_args: self._notify_change())
        for widget in (self.summary_box, self.objective_box, self.thread_box):
            widget.bind("<KeyRelease>", lambda _event: self._notify_change())

    def _textbox(self, label: str, *, height: int = 84):
        ctk.CTkLabel(self, text=label, text_color=EDITOR_PALETTE["text"]).pack(anchor="w", padx=12)
        box = ctk.CTkTextbox(self, height=height, fg_color=EDITOR_PALETTE["surface"], border_width=1, border_color=EDITOR_PALETTE["border"])
        box.pack(fill="x", padx=12, pady=(2, 8))
        return box

    def _build_scenarios_editor(self):
        ctk.CTkLabel(self, text="Linked Scenarios", text_color=EDITOR_PALETTE["text"]).pack(anchor="w", padx=12)

        scenarios_panel = ctk.CTkFrame(
            self,
            fg_color=EDITOR_PALETTE["surface"],
            border_width=1,
            border_color=EDITOR_PALETTE["border"],
            corner_radius=8,
        )
        scenarios_panel.pack(fill="x", padx=12, pady=(2, 8))
        scenarios_panel.grid_columnconfigure(0, weight=1)
        scenarios_panel.grid_rowconfigure(0, weight=1)

        self.scenarios_list = tk.Listbox(
            scenarios_panel,
            activestyle="none",
            height=7,
            bg=EDITOR_PALETTE["surface"],
            fg=EDITOR_PALETTE["text"],
            selectbackground=EDITOR_PALETTE["accent"],
            selectforeground=EDITOR_PALETTE["text"],
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            exportselection=False,
        )
        self.scenarios_list.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        self.scenarios_list.bind("<<ListboxSelect>>", lambda _event: self._sync_remove_button_state())
        self.scenarios_list.bind("<Delete>", lambda _event: self._remove_selected_scenario())

        actions = ctk.CTkFrame(scenarios_panel, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="ns", padx=(6, 6), pady=6)
        self.remove_scenario_btn = ctk.CTkButton(
            actions,
            text="Delete selected",
            width=118,
            command=self._remove_selected_scenario,
        )
        self.remove_scenario_btn.pack(anchor="n")

        add_row = ctk.CTkFrame(self, fg_color="transparent")
        add_row.pack(fill="x", padx=12, pady=(0, 8))
        self.scenario_entry = ctk.CTkEntry(
            add_row,
            textvariable=self.scenario_entry_var,
            placeholder_text="Add a scenario title",
            **toolbar_entry_style(),
        )
        self.scenario_entry.pack(side="left", fill="x", expand=True)
        self.add_scenario_btn = ctk.CTkButton(add_row, text="Add", width=80, command=self._add_scenario_from_entry)
        self.add_scenario_btn.pack(side="left", padx=(8, 0))
        self.scenario_entry.bind("<Return>", lambda _event: self._add_scenario_from_entry())

    def set_arc(self, arc: dict | None):
        self._is_loading = True
        try:
            self._set_text(self.name_entry, self.name_var, (arc or {}).get("name") or "")
            self.status_var.set(canonicalize_arc_status((arc or {}).get("status")))
            self._set_box(self.summary_box, (arc or {}).get("summary") or "")
            self._set_box(self.objective_box, (arc or {}).get("objective") or "")
            self._set_box(self.thread_box, (arc or {}).get("thread") or "")
            scenarios = [str(item).strip() for item in ((arc or {}).get("scenarios") or []) if str(item).strip()]
            self._set_scenarios(scenarios)
            self._refresh_validation(arc)
            self._set_enabled(bool(arc))
        finally:
            self._is_loading = False

    def get_arc_data(self) -> dict:
        return {
            "name": self.name_var.get().strip(),
            "summary": self.summary_box.get("1.0", "end").strip(),
            "objective": self.objective_box.get("1.0", "end").strip(),
            "thread": self.thread_box.get("1.0", "end").strip(),
            "status": canonicalize_arc_status(self.status_var.get()),
            "scenarios": list(self._scenario_items),
        }

    def _notify_change(self):
        if self._is_loading:
            return
        self._on_change()

    def _set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.name_entry.configure(state=state)
        self.status_menu.configure(state=state)
        for box in (self.summary_box, self.objective_box, self.thread_box):
            box.configure(state=state)
        self.scenario_entry.configure(state=state)
        self.add_scenario_btn.configure(state=state)
        self.scenarios_list.configure(state=state)
        self._sync_remove_button_state()

    def _refresh_validation(self, arc: dict | None):
        if not arc:
            self.validation_label.configure(text="Select an arc to edit details.")
            return
        issues: list[str] = []
        if not str(arc.get("name") or "").strip():
            issues.append("• Arc name is required")
        if not str(arc.get("objective") or "").strip():
            issues.append("• Objective is empty")
        if not (arc.get("scenarios") or []):
            issues.append("• No linked scenarios")
        self.validation_label.configure(text="\n".join(issues) if issues else "Arc looks good for generation.")

    @staticmethod
    def _set_box(box: ctk.CTkTextbox, value: str):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", value)

    @staticmethod
    def _set_text(entry: ctk.CTkEntry, variable: tk.StringVar, value: str):
        entry.configure(state="normal")
        variable.set(value)

    def _set_scenarios(self, scenarios: list[str]):
        self._scenario_items = list(dict.fromkeys(str(item).strip() for item in scenarios if str(item).strip()))
        self.scenarios_list.delete(0, tk.END)
        for scenario in self._scenario_items:
            self.scenarios_list.insert(tk.END, scenario)
        self._sync_remove_button_state()

    def _sync_remove_button_state(self):
        selected = bool(self.scenarios_list.curselection())
        is_enabled = str(self.scenarios_list.cget("state")) == "normal"
        self.remove_scenario_btn.configure(state="normal" if selected and is_enabled else "disabled")

    def _add_scenario_from_entry(self):
        title = self.scenario_entry_var.get().strip()
        if not title or title in self._scenario_items:
            return
        self._scenario_items.append(title)
        self.scenarios_list.insert(tk.END, title)
        self.scenario_entry_var.set("")
        self._sync_remove_button_state()
        self._notify_change()

    def _remove_selected_scenario(self):
        selection = self.scenarios_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index < 0 or index >= len(self._scenario_items):
            return
        del self._scenario_items[index]
        self.scenarios_list.delete(index)
        if self._scenario_items:
            new_index = min(index, len(self._scenario_items) - 1)
            self.scenarios_list.selection_set(new_index)
        self._sync_remove_button_state()
        self._notify_change()
