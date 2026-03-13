from __future__ import annotations

import json
import customtkinter as ctk
from tkinter import messagebox

from modules.campaigns.services.campaign_payload_builder import build_campaign_payload
from modules.campaigns.ui.arc_editor_dialog import ArcEditorDialog
from modules.campaigns.ui.widgets import CampaignDateField
from modules.generic.editor.styles import (
    EDITOR_PALETTE,
    option_menu_style,
    primary_button_style,
    section_style,
    toolbar_entry_style,
)


class CampaignBuilderWizard(ctk.CTkToplevel):
    """Three-step wizard helping GMs structure campaigns and internal arcs."""

    def __init__(self, master, campaign_wrapper, scenario_wrapper):
        super().__init__(master)
        self.title("Campaign Builder Wizard")
        self.geometry("980x760")
        self.configure(fg_color=EDITOR_PALETTE["surface"])

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
        root = ctk.CTkFrame(self, fg_color=EDITOR_PALETTE["surface"])
        root.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            root,
            text="Campaign Organization Wizard",
            font=("Arial", 20, "bold"),
            text_color=EDITOR_PALETTE["text"],
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            root,
            text="Create the foundation, arcs, and summary in the same visual style as the entity editor.",
            text_color=EDITOR_PALETTE["muted_text"],
        ).pack(anchor="w", pady=(0, 10))

        self.content = ctk.CTkFrame(root, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        self.steps = [
            self._build_foundation_step(self.content),
            self._build_arcs_step(self.content),
            self._build_review_step(self.content),
        ]

        nav = ctk.CTkFrame(root, fg_color="transparent")
        nav.pack(fill="x", pady=(10, 0))
        self.back_btn = ctk.CTkButton(nav, text="Back", command=self._go_back, **primary_button_style())
        self.back_btn.pack(side="left")
        self.next_btn = ctk.CTkButton(nav, text="Next", command=self._go_next, **primary_button_style())
        self.next_btn.pack(side="right", padx=6)
        ctk.CTkButton(
            nav,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=EDITOR_PALETTE["border"],
        ).pack(side="right", padx=6)

    def _build_foundation_step(self, parent):
        frame = ctk.CTkFrame(parent, **section_style())
        frame.pack_propagate(False)

        self.form_vars = {
            "name": ctk.StringVar(),
            "genre": ctk.StringVar(),
            "tone": ctk.StringVar(),
            "status": ctk.StringVar(value="Planned"),
        }

        ctk.CTkLabel(
            frame,
            text="Campaign Foundation",
            font=("Arial", 16, "bold"),
            text_color=EDITOR_PALETTE["text"],
        ).pack(anchor="w", padx=12, pady=(12, 8))

        form_body = ctk.CTkFrame(frame, fg_color="transparent")
        form_body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        row1 = ctk.CTkFrame(form_body, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        self._labeled_entry(row1, "Campaign Name", "name", 0)
        self._labeled_entry(row1, "Genre", "genre", 1)

        row2 = ctk.CTkFrame(form_body, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        self._labeled_entry(row2, "Tone", "tone", 0)
        ctk.CTkLabel(row2, text="Status", text_color=EDITOR_PALETTE["text"]).grid(row=0, column=1, sticky="w", padx=(8, 4))
        ctk.CTkOptionMenu(
            row2,
            variable=self.form_vars["status"],
            values=["Planned", "Running", "Paused", "Completed"],
            **option_menu_style(),
        ).grid(
            row=1, column=1, sticky="ew", padx=(8, 4)
        )
        row2.grid_columnconfigure(0, weight=1)
        row2.grid_columnconfigure(1, weight=1)

        row3 = ctk.CTkFrame(form_body, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        self.start_date_field = CampaignDateField(row3, label="Start Date")
        self.start_date_field.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.end_date_field = CampaignDateField(row3, label="End Date")
        self.end_date_field.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        row3.grid_columnconfigure(0, weight=1)
        row3.grid_columnconfigure(1, weight=1)

        self.logline_box = self._labeled_box(form_body, "Logline", 90)
        self.setting_box = self._labeled_box(form_body, "Setting", 100)
        self.objective_box = self._labeled_box(form_body, "Main Objective", 90)
        self.stakes_box = self._labeled_box(form_body, "Stakes", 90)
        self.themes_box = self._labeled_box(form_body, "Themes (one per line)", 80)
        self.notes_box = self._labeled_box(form_body, "Notes", 90)

        return frame

    def _build_arcs_step(self, parent):
        frame = ctk.CTkFrame(parent, **section_style())
        ctk.CTkLabel(frame, text="Arcs Planner", font=("Arial", 16, "bold"), text_color=EDITOR_PALETTE["text"]).pack(anchor="w", pady=(12, 6), padx=12)

        self.arcs_list = ctk.CTkTextbox(frame, height=420, fg_color=EDITOR_PALETTE["surface_soft"], border_width=1, border_color=EDITOR_PALETTE["border"])
        self.arcs_list.pack(fill="both", expand=True, padx=12)
        self.arcs_list.configure(state="disabled")

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 12), padx=12)
        ctk.CTkButton(buttons, text="Add Arc", command=self._add_arc, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Edit Last Arc", command=self._edit_last_arc, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Remove Last Arc", command=self._remove_last_arc, **primary_button_style()).pack(side="left", padx=4)

        return frame

    def _build_review_step(self, parent):
        frame = ctk.CTkFrame(parent, **section_style())
        ctk.CTkLabel(frame, text="Review", font=("Arial", 16, "bold"), text_color=EDITOR_PALETTE["text"]).pack(anchor="w", pady=(12, 6), padx=12)
        self.review_box = ctk.CTkTextbox(frame, height=520, fg_color=EDITOR_PALETTE["surface_soft"], border_width=1, border_color=EDITOR_PALETTE["border"])
        self.review_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.review_box.configure(state="disabled")
        return frame

    def _labeled_entry(self, parent, label: str, key: str, col: int):
        ctk.CTkLabel(parent, text=label, text_color=EDITOR_PALETTE["text"]).grid(row=0, column=col, sticky="w", padx=(8 if col else 0, 4))
        ctk.CTkEntry(parent, textvariable=self.form_vars[key], **toolbar_entry_style()).grid(row=1, column=col, sticky="ew", padx=(8 if col else 0, 4))
        parent.grid_columnconfigure(col, weight=1)

    def _labeled_box(self, parent, label: str, height: int):
        ctk.CTkLabel(parent, text=label, text_color=EDITOR_PALETTE["text"]).pack(anchor="w")
        box = ctk.CTkTextbox(parent, height=height, fg_color=EDITOR_PALETTE["surface_soft"], border_width=1, border_color=EDITOR_PALETTE["border"])
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
            "campaign": {
                **{k: var.get().strip() for k, var in self.form_vars.items()},
                "start_date": self.start_date_field.get(),
                "end_date": self.end_date_field.get(),
            },
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
                    "start_date": self.start_date_field.get(),
                    "end_date": self.end_date_field.get(),
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
