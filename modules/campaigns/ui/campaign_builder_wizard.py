from __future__ import annotations

import json
import customtkinter as ctk
from tkinter import messagebox

from modules.campaigns.services.campaign_payload_builder import build_campaign_payload
from modules.campaigns.ui.arc_editor_dialog import ArcEditorDialog


class CampaignBuilderWizard(ctk.CTkToplevel):
    """Three-step wizard helping GMs structure campaigns and internal arcs."""

    def __init__(self, master, campaign_wrapper, scenario_wrapper):
        super().__init__(master)
        self.title("Campaign Builder Wizard")
        self.geometry("980x760")

        self.campaign_wrapper = campaign_wrapper
        self.scenario_titles = self._load_scenario_titles(scenario_wrapper)

        self.arcs: list[dict] = []
        self.current_step = 0
        self.steps: list[ctk.CTkFrame] = []

        self._build_layout()
        self._show_step(0)

        self.transient(master)
        self.grab_set()
        self.focus_force()

    def _build_layout(self):
        root = ctk.CTkFrame(self)
        root.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(root, text="Campaign Organization Wizard", font=("Arial", 20, "bold")).pack(anchor="w", pady=(0, 8))

        self.content = ctk.CTkFrame(root)
        self.content.pack(fill="both", expand=True)

        self.steps = [
            self._build_foundation_step(self.content),
            self._build_arcs_step(self.content),
            self._build_review_step(self.content),
        ]

        nav = ctk.CTkFrame(root, fg_color="transparent")
        nav.pack(fill="x", pady=(10, 0))
        self.back_btn = ctk.CTkButton(nav, text="Back", command=self._go_back)
        self.back_btn.pack(side="left")
        self.next_btn = ctk.CTkButton(nav, text="Next", command=self._go_next)
        self.next_btn.pack(side="right", padx=6)
        ctk.CTkButton(nav, text="Cancel", command=self.destroy).pack(side="right", padx=6)

    def _build_foundation_step(self, parent):
        frame = ctk.CTkFrame(parent)

        self.form_vars = {
            "name": ctk.StringVar(),
            "genre": ctk.StringVar(),
            "tone": ctk.StringVar(),
            "status": ctk.StringVar(value="Planned"),
            "start_date": ctk.StringVar(),
            "end_date": ctk.StringVar(),
        }

        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        self._labeled_entry(row1, "Campaign Name", "name", 0)
        self._labeled_entry(row1, "Genre", "genre", 1)

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        self._labeled_entry(row2, "Tone", "tone", 0)
        ctk.CTkLabel(row2, text="Status").grid(row=0, column=1, sticky="w", padx=(8, 4))
        ctk.CTkOptionMenu(row2, variable=self.form_vars["status"], values=["Planned", "Running", "Paused", "Completed"]).grid(
            row=1, column=1, sticky="ew", padx=(8, 4)
        )
        row2.grid_columnconfigure(0, weight=1)
        row2.grid_columnconfigure(1, weight=1)

        row3 = ctk.CTkFrame(frame, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        self._labeled_entry(row3, "Start Date", "start_date", 0)
        self._labeled_entry(row3, "End Date", "end_date", 1)

        self.logline_box = self._labeled_box(frame, "Logline", 90)
        self.setting_box = self._labeled_box(frame, "Setting", 100)
        self.objective_box = self._labeled_box(frame, "Main Objective", 90)
        self.stakes_box = self._labeled_box(frame, "Stakes", 90)
        self.themes_box = self._labeled_box(frame, "Themes (one per line)", 80)
        self.notes_box = self._labeled_box(frame, "Notes", 90)

        return frame

    def _build_arcs_step(self, parent):
        frame = ctk.CTkFrame(parent)
        ctk.CTkLabel(frame, text="Arcs Planner", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 6))

        self.arcs_list = ctk.CTkTextbox(frame, height=420)
        self.arcs_list.pack(fill="both", expand=True)
        self.arcs_list.configure(state="disabled")

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(buttons, text="Add Arc", command=self._add_arc).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Edit Last Arc", command=self._edit_last_arc).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Remove Last Arc", command=self._remove_last_arc).pack(side="left", padx=4)

        return frame

    def _build_review_step(self, parent):
        frame = ctk.CTkFrame(parent)
        ctk.CTkLabel(frame, text="Review", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 6))
        self.review_box = ctk.CTkTextbox(frame, height=520)
        self.review_box.pack(fill="both", expand=True)
        self.review_box.configure(state="disabled")
        return frame

    def _labeled_entry(self, parent, label: str, key: str, col: int):
        ctk.CTkLabel(parent, text=label).grid(row=0, column=col, sticky="w", padx=(8 if col else 0, 4))
        ctk.CTkEntry(parent, textvariable=self.form_vars[key]).grid(row=1, column=col, sticky="ew", padx=(8 if col else 0, 4))
        parent.grid_columnconfigure(col, weight=1)

    def _labeled_box(self, parent, label: str, height: int):
        ctk.CTkLabel(parent, text=label).pack(anchor="w")
        box = ctk.CTkTextbox(parent, height=height)
        box.pack(fill="x", pady=(0, 8))
        return box

    def _show_step(self, index: int):
        self.current_step = max(0, min(index, len(self.steps) - 1))
        for idx, frame in enumerate(self.steps):
            if idx == self.current_step:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        self.back_btn.configure(state="normal" if self.current_step > 0 else "disabled")
        if self.current_step == len(self.steps) - 1:
            self.next_btn.configure(text="Save Campaign", command=self._save_campaign)
            self._refresh_review()
        else:
            self.next_btn.configure(text="Next", command=self._go_next)

    def _go_back(self):
        self._show_step(self.current_step - 1)

    def _go_next(self):
        if self.current_step == 0 and not self.form_vars["name"].get().strip():
            messagebox.showwarning("Missing data", "Campaign name is required.", parent=self)
            return
        self._show_step(self.current_step + 1)

    def _add_arc(self):
        dlg = ArcEditorDialog(self, self.scenario_titles)
        self.wait_window(dlg)
        if dlg.result:
            self.arcs.append(dlg.result)
            self._refresh_arcs_preview()

    def _edit_last_arc(self):
        if not self.arcs:
            messagebox.showinfo("No arc", "Add at least one arc first.", parent=self)
            return
        dlg = ArcEditorDialog(self, self.scenario_titles, initial_data=self.arcs[-1])
        self.wait_window(dlg)
        if dlg.result:
            self.arcs[-1] = dlg.result
            self._refresh_arcs_preview()

    def _remove_last_arc(self):
        if self.arcs:
            self.arcs.pop()
            self._refresh_arcs_preview()

    def _refresh_arcs_preview(self):
        self.arcs_list.configure(state="normal")
        self.arcs_list.delete("1.0", "end")
        if not self.arcs:
            self.arcs_list.insert("end", "No arc yet. Add one to structure your campaign progression.")
        for idx, arc in enumerate(self.arcs, start=1):
            self.arcs_list.insert("end", f"{idx}. {arc.get('name')} [{arc.get('status', 'Planned')}]\n")
            self.arcs_list.insert("end", f"   Objective: {arc.get('objective', '')}\n")
            self.arcs_list.insert("end", f"   Scenarios: {', '.join(arc.get('scenarios') or [])}\n\n")
        self.arcs_list.configure(state="disabled")

    def _refresh_review(self):
        summary = {
            "campaign": {k: var.get().strip() for k, var in self.form_vars.items()},
            "arcs": self.arcs,
            "logline": self.logline_box.get("1.0", "end").strip(),
            "setting": self.setting_box.get("1.0", "end").strip(),
            "objective": self.objective_box.get("1.0", "end").strip(),
            "stakes": self.stakes_box.get("1.0", "end").strip(),
            "themes": self.themes_box.get("1.0", "end").strip(),
            "notes": self.notes_box.get("1.0", "end").strip(),
        }
        self.review_box.configure(state="normal")
        self.review_box.delete("1.0", "end")
        self.review_box.insert("end", json.dumps(summary, indent=2, ensure_ascii=False))
        self.review_box.configure(state="disabled")

    def _save_campaign(self):
        try:
            payload = build_campaign_payload(
                form_data={
                    **{k: var.get() for k, var in self.form_vars.items()},
                    "logline": self.logline_box.get("1.0", "end").strip(),
                    "setting": self.setting_box.get("1.0", "end").strip(),
                    "main_objective": self.objective_box.get("1.0", "end").strip(),
                    "stakes": self.stakes_box.get("1.0", "end").strip(),
                    "themes": self.themes_box.get("1.0", "end").strip(),
                    "notes": self.notes_box.get("1.0", "end").strip(),
                },
                arcs_data=self.arcs,
            )
            self.campaign_wrapper.save_item(payload, key_field="Name")
        except Exception as exc:
            messagebox.showerror("Save failed", f"Unable to save campaign: {exc}", parent=self)
            return

        messagebox.showinfo("Campaign saved", f"Campaign '{payload['Name']}' has been saved.", parent=self)
        self.destroy()

    @staticmethod
    def _load_scenario_titles(scenario_wrapper) -> list[str]:
        try:
            scenarios = scenario_wrapper.load_items() if scenario_wrapper else []
        except Exception:
            return []
        titles = []
        for scenario in scenarios:
            title = (scenario.get("Title") or scenario.get("Name") or "").strip()
            if title and title not in titles:
                titles.append(title)
        return titles
