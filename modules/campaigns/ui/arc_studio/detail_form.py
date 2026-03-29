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
        self.scenarios_box = self._textbox("Linked Scenarios (one title per line)", height=110)

        self.validation_label = ctk.CTkLabel(self, text="", text_color=EDITOR_PALETTE["muted_text"], justify="left")
        self.validation_label.pack(anchor="w", padx=12, pady=(4, 12))

        self.name_var.trace_add("write", lambda *_args: self._notify_change())
        for widget in (self.summary_box, self.objective_box, self.thread_box, self.scenarios_box):
            widget.bind("<KeyRelease>", lambda _event: self._notify_change())

    def _textbox(self, label: str, *, height: int = 84):
        ctk.CTkLabel(self, text=label, text_color=EDITOR_PALETTE["text"]).pack(anchor="w", padx=12)
        box = ctk.CTkTextbox(self, height=height, fg_color=EDITOR_PALETTE["surface"], border_width=1, border_color=EDITOR_PALETTE["border"])
        box.pack(fill="x", padx=12, pady=(2, 8))
        return box

    def set_arc(self, arc: dict | None):
        self._is_loading = True
        try:
            self._set_text(self.name_entry, self.name_var, (arc or {}).get("name") or "")
            self.status_var.set(canonicalize_arc_status((arc or {}).get("status")))
            self._set_box(self.summary_box, (arc or {}).get("summary") or "")
            self._set_box(self.objective_box, (arc or {}).get("objective") or "")
            self._set_box(self.thread_box, (arc or {}).get("thread") or "")
            scenarios = [str(item).strip() for item in ((arc or {}).get("scenarios") or []) if str(item).strip()]
            self._set_box(self.scenarios_box, "\n".join(scenarios))
            self._refresh_validation(arc)
            self._set_enabled(bool(arc))
        finally:
            self._is_loading = False

    def get_arc_data(self) -> dict:
        scenarios = [line.strip() for line in self.scenarios_box.get("1.0", "end").splitlines() if line.strip()]
        return {
            "name": self.name_var.get().strip(),
            "summary": self.summary_box.get("1.0", "end").strip(),
            "objective": self.objective_box.get("1.0", "end").strip(),
            "thread": self.thread_box.get("1.0", "end").strip(),
            "status": canonicalize_arc_status(self.status_var.get()),
            "scenarios": list(dict.fromkeys(scenarios)),
        }

    def _notify_change(self):
        if self._is_loading:
            return
        self._on_change()

    def _set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.name_entry.configure(state=state)
        self.status_menu.configure(state=state)
        for box in (self.summary_box, self.objective_box, self.thread_box, self.scenarios_box):
            box.configure(state=state)

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
