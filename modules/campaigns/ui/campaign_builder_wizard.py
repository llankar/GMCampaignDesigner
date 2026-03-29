from __future__ import annotations

import json
import re
import time
import customtkinter as ctk
from tkinter import messagebox

from modules.campaigns.services import (
    ArcGenerationService,
    ArcScenarioExpansionService,
    ArcScenarioExpansionValidationError,
    CampaignForgePersistence,
    CampaignForgePersistenceError,
    SAVE_MODE_MERGE_KEEP_EXISTING,
    SAVE_MODE_REPLACE_GENERATED_ONLY,
    build_campaign_payload,
    build_form_state_from_campaign,
    list_campaign_presets,
)
from modules.campaigns.services.ai.arc_scenario_entities import load_existing_entity_catalog
from modules.campaigns.shared.arc_status import canonicalize_arc_status
from modules.campaigns.ui.arc_editor_dialog import ArcEditorDialog
from modules.campaigns.ui.campaign_forge_preview_dialog import preview_campaign_forge_payload
from modules.campaigns.ui.widgets import CampaignDateField
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.logging_helper import log_error, log_exception, log_info, log_warning
from modules.helpers.template_loader import load_template
from modules.helpers.window_helper import position_window_at_top
from modules.scenarios.scenario_builder_wizard import ScenarioBuilderWizard
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
        self.geometry("1480x1040")
        self.configure(fg_color=EDITOR_PALETTE["surface"])

        self.campaign_wrapper = campaign_wrapper
        self.scenario_wrapper = scenario_wrapper
        self.scenario_titles = self._load_scenario_titles(scenario_wrapper)
        self.available_presets = list_campaign_presets()
        self.preset_by_id = {preset["id"]: preset for preset in self.available_presets}
        self.selected_preset_id: str | None = None

        self.arcs: list[dict] = []
        self.current_arc_index: int | None = None
        self._arc_line_ranges: list[tuple[int, int, int]] = []
        self.original_campaign_name: str | None = None
        self._ai_client = None
        self._last_unsaved_generated_payload: dict | None = None
        self.current_step = 0
        self.steps: list[ctk.CTkFrame] = []
        self._interactive_controls: list[ctk.CTkBaseClass] = []

        self._build_layout()
        self._show_step(0)

        self.transient(master)
        self.grab_set()
        self.focus_force()
        position_window_at_top(self)

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

        load_row = ctk.CTkFrame(root, fg_color="transparent")
        load_row.pack(fill="x", pady=(0, 8))
        self.load_campaign_btn = ctk.CTkButton(
            load_row,
            text="Load Existing Campaign",
            command=self._load_existing_campaign,
            **primary_button_style(),
        )
        self.load_campaign_btn.pack(side="left")
        self._register_interactive_control(self.load_campaign_btn)

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
        self.cancel_btn = ctk.CTkButton(
            nav,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=EDITOR_PALETTE["border"],
        )
        self.cancel_btn.pack(side="right", padx=6)
        self._register_interactive_control(self.back_btn, self.next_btn, self.cancel_btn)

    def _build_foundation_step(self, parent):
        frame = ctk.CTkFrame(parent, **section_style())
        frame.pack_propagate(False)

        scrollable = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scrollable.pack(fill="both", expand=True, padx=4, pady=4)

        self.form_vars = {
            "name": ctk.StringVar(),
            "genre": ctk.StringVar(),
            "tone": ctk.StringVar(),
            "status": ctk.StringVar(value="Planned"),
        }

        ctk.CTkLabel(
            scrollable,
            text="Campaign Foundation",
            font=("Arial", 16, "bold"),
            text_color=EDITOR_PALETTE["text"],
        ).pack(anchor="w", padx=12, pady=(12, 8))

        preset_row = ctk.CTkFrame(scrollable, fg_color="transparent")
        preset_row.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(preset_row, text="Preset", text_color=EDITOR_PALETTE["text"]).pack(anchor="w")

        preset_labels = self._preset_option_labels()
        default_preset_label = preset_labels[0] if preset_labels else "No preset available"
        self.preset_var = ctk.StringVar(value=default_preset_label)
        self.preset_menu = ctk.CTkOptionMenu(
            preset_row,
            variable=self.preset_var,
            values=preset_labels or ["No preset available"],
            command=self._on_preset_selected,
            **option_menu_style(),
        )
        self.preset_menu.pack(fill="x", pady=(4, 0))

        self.preset_description_label = ctk.CTkLabel(
            preset_row,
            text="",
            text_color=EDITOR_PALETTE["muted_text"],
            justify="left",
            wraplength=820,
        )
        self.preset_description_label.pack(anchor="w", pady=(4, 0))
        self._refresh_preset_description()

        form_body = ctk.CTkFrame(scrollable, fg_color="transparent")
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

    def _preset_option_labels(self) -> list[str]:
        labels = ["No preset"]
        labels.extend(f"{preset['name']} ({preset['id']})" for preset in self.available_presets)
        return labels

    def _preset_option_to_id(self, option_label: str) -> str | None:
        if not option_label or option_label == "No preset":
            return None
        if option_label.endswith(")") and "(" in option_label:
            return option_label.rsplit("(", 1)[1].rstrip(")").strip() or None
        return None

    def _refresh_preset_description(self):
        if not hasattr(self, "preset_description_label"):
            return
        preset = self.preset_by_id.get(self.selected_preset_id) if self.selected_preset_id else None
        if not preset:
            self.preset_description_label.configure(text="Choose a preset to pre-fill tone, themes, and default arc structure.")
            return
        description = preset.get("description") or "No description."
        self.preset_description_label.configure(text=f"Preset: {description}")

    def _on_preset_selected(self, value: str):
        preset_id = self._preset_option_to_id(value)
        if preset_id == self.selected_preset_id:
            return

        if not preset_id:
            self.selected_preset_id = None
            self._refresh_preset_description()
            return

        preset = self.preset_by_id.get(preset_id)
        if not preset:
            return

        touched_fields, touched_arcs = self._detect_manual_modifications()
        if touched_fields or touched_arcs:
            proceed = messagebox.askyesno(
                "Apply preset",
                "Some fields/arcs were already modified. Apply the preset without overwriting modified values?",
                parent=self,
            )
            if not proceed:
                self._restore_selected_preset_label()
                return

        self._apply_preset(preset, touched_fields=touched_fields, preserve_arcs=touched_arcs)
        self.selected_preset_id = preset_id
        self._refresh_preset_description()

    def _restore_selected_preset_label(self):
        if not hasattr(self, "preset_var"):
            return
        if not self.selected_preset_id:
            self.preset_var.set("No preset")
            return
        preset = self.preset_by_id.get(self.selected_preset_id)
        self.preset_var.set(f"{preset['name']} ({preset['id']})" if preset else "No preset")

    def _detect_manual_modifications(self) -> tuple[set[str], bool]:
        touched_fields: set[str] = set()

        for key in ("name", "genre", "tone", "status"):
            if self.form_vars[key].get().strip():
                touched_fields.add(key)

        if self.start_date_field.get().strip():
            touched_fields.add("start_date")
        if self.end_date_field.get().strip():
            touched_fields.add("end_date")

        textboxes = {
            "logline": self.logline_box,
            "setting": self.setting_box,
            "main_objective": self.objective_box,
            "stakes": self.stakes_box,
            "themes": self.themes_box,
            "notes": self.notes_box,
        }
        for key, widget in textboxes.items():
            if widget.get("1.0", "end").strip():
                touched_fields.add(key)

        return touched_fields, bool(self.arcs)

    def _apply_preset(self, preset: dict, touched_fields: set[str], preserve_arcs: bool):
        for key, value in (preset.get("form") or {}).items():
            if key in touched_fields:
                continue
            if key in self.form_vars:
                self.form_vars[key].set(value)

        if "start_date" in (preset.get("form") or {}) and "start_date" not in touched_fields:
            self.start_date_field.set((preset.get("form") or {}).get("start_date", ""))
        if "end_date" in (preset.get("form") or {}) and "end_date" not in touched_fields:
            self.end_date_field.set((preset.get("form") or {}).get("end_date", ""))

        text_widgets = {
            "logline": self.logline_box,
            "setting": self.setting_box,
            "main_objective": self.objective_box,
            "stakes": self.stakes_box,
            "themes": self.themes_box,
            "notes": self.notes_box,
        }
        for key, value in (preset.get("text_areas") or {}).items():
            if key in touched_fields:
                continue
            widget = text_widgets.get(key)
            if widget is not None:
                self._set_textbox_value(widget, value)

        if not preserve_arcs:
            self.arcs = [dict(arc) for arc in (preset.get("arcs") or [])]
            self.current_arc_index = 0 if self.arcs else None
            self._refresh_arcs_preview()

    def _build_arcs_step(self, parent):
        frame = ctk.CTkFrame(parent, **section_style())
        ctk.CTkLabel(frame, text="Arcs Planner", font=("Arial", 16, "bold"), text_color=EDITOR_PALETTE["text"]).pack(anchor="w", pady=(12, 6), padx=12)

        self.arcs_list = ctk.CTkTextbox(frame, height=420, fg_color=EDITOR_PALETTE["surface_soft"], border_width=1, border_color=EDITOR_PALETTE["border"])
        self.arcs_list.pack(fill="both", expand=True, padx=12)
        self.arcs_list.bind("<Button-1>", self._on_arcs_preview_click)
        self.arcs_list.bind("<Double-Button-1>", self._on_arcs_preview_double_click)
        self.arcs_list.configure(state="disabled", cursor="hand2")

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 12), padx=12)
        buttons.grid_columnconfigure(0, weight=1)

        top_button_row = ctk.CTkFrame(buttons, fg_color="transparent")
        top_button_row.grid(row=0, column=0, sticky="w")
        bottom_button_row = ctk.CTkFrame(buttons, fg_color="transparent")
        bottom_button_row.grid(row=1, column=0, sticky="w", pady=(6, 0))

        self.add_arc_btn = ctk.CTkButton(top_button_row, text="Add Arc", command=self._add_arc, **primary_button_style())
        self.generate_arcs_btn = ctk.CTkButton(top_button_row, text="Generate Arcs from Scenarios", command=self._generate_arcs_from_scenarios, **primary_button_style())
        self.generate_scenarios_btn = ctk.CTkButton(top_button_row, text="Generate 2 Scenarios per Arc", command=self._generate_scenarios_per_arc, **primary_button_style())
        self.generate_validate_btn = ctk.CTkButton(
            top_button_row,
            text="Generate + Validate Scenes (DB)",
            command=self._generate_db_aware_scenarios_per_arc,
            **primary_button_style(),
        )
        self.forge_campaign_btn = ctk.CTkButton(
            top_button_row,
            text="Forge Full Campaign",
            command=self._forge_full_campaign,
            **primary_button_style(),
        )
        self.edit_arc_btn = ctk.CTkButton(top_button_row, text="Edit Arc", command=self._edit_selected_arc, **primary_button_style())
        self.create_scenario_btn = ctk.CTkButton(
            bottom_button_row,
            text="Create Scenario for selected arc",
            command=self._create_scenario_for_selected_arc,
            **primary_button_style(),
        )
        self.move_up_btn = ctk.CTkButton(bottom_button_row, text="Move Up", command=self._move_arc_up, **primary_button_style())
        self.move_down_btn = ctk.CTkButton(bottom_button_row, text="Move Down", command=self._move_arc_down, **primary_button_style())
        self.duplicate_arc_btn = ctk.CTkButton(bottom_button_row, text="Duplicate", command=self._duplicate_selected_arc, **primary_button_style())
        self.delete_arc_btn = ctk.CTkButton(bottom_button_row, text="Delete", command=self._delete_selected_arc, **primary_button_style())

        for button in (
            self.add_arc_btn,
            self.generate_arcs_btn,
            self.generate_scenarios_btn,
            self.generate_validate_btn,
            self.forge_campaign_btn,
            self.edit_arc_btn,
            self.create_scenario_btn,
            self.move_up_btn,
            self.move_down_btn,
            self.duplicate_arc_btn,
            self.delete_arc_btn,
        ):
            button.pack(side="left", padx=4)
        self._register_interactive_control(
            self.add_arc_btn,
            self.generate_arcs_btn,
            self.generate_scenarios_btn,
            self.generate_validate_btn,
            self.forge_campaign_btn,
            self.edit_arc_btn,
            self.create_scenario_btn,
            self.move_up_btn,
            self.move_down_btn,
            self.duplicate_arc_btn,
            self.delete_arc_btn,
        )

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
            self.current_arc_index = len(self.arcs) - 1
            self._refresh_arcs_preview()

    def _edit_selected_arc(self):
        selected_index = self._get_selected_arc_index()
        if selected_index is None:
            messagebox.showinfo("No arc", "Add at least one arc first.", parent=self)
            return
        dlg = ArcEditorDialog(self, self.scenario_titles, initial_data=self.arcs[selected_index])
        self.wait_window(dlg)
        if dlg.result:
            self.arcs[selected_index] = dlg.result
            self.current_arc_index = selected_index
            self._refresh_arcs_preview()

    def _create_scenario_for_selected_arc(self):
        selected_index = self._get_selected_arc_index()
        if selected_index is None:
            messagebox.showinfo("No arc", "Select or add an arc first.", parent=self)
            return

        arc = self.arcs[selected_index]
        campaign_context = {
            "name": self.form_vars["name"].get().strip(),
            "summary": self.logline_box.get("1.0", "end").strip(),
        }

        def _on_embedded_result(payload):
            self._on_embedded_scenario_created(payload, selected_index)

        wizard = ScenarioBuilderWizard(
            self,
            mode="embedded",
            campaign_context=campaign_context,
            arc_context=arc,
            on_embedded_result=_on_embedded_result,
        )
        wizard.grab_set()
        wizard.focus_force()

    def _on_embedded_scenario_created(self, payload: dict, arc_index: int):
        if arc_index < 0 or arc_index >= len(self.arcs):
            return
        scenario = (payload or {}).get("scenario") or {}
        title = str((payload or {}).get("scenario_title") or scenario.get("Title") or "").strip()
        if not title:
            return

        arc = self.arcs[arc_index]
        scenarios = [str(name).strip() for name in (arc.get("scenarios") or []) if str(name).strip()]
        if title not in scenarios:
            scenarios.append(title)
        arc["scenarios"] = list(dict.fromkeys(scenarios))
        self.scenario_titles = list(dict.fromkeys([*self.scenario_titles, title]))
        self.current_arc_index = arc_index
        self._refresh_arcs_preview()
        self._refresh_review()

    def _move_arc_up(self):
        selected_index = self._get_selected_arc_index()
        if selected_index is None or selected_index == 0:
            return
        self.arcs[selected_index - 1], self.arcs[selected_index] = self.arcs[selected_index], self.arcs[selected_index - 1]
        self.current_arc_index = selected_index - 1
        self._refresh_arcs_preview()

    def _move_arc_down(self):
        selected_index = self._get_selected_arc_index()
        if selected_index is None or selected_index >= len(self.arcs) - 1:
            return
        self.arcs[selected_index + 1], self.arcs[selected_index] = self.arcs[selected_index], self.arcs[selected_index + 1]
        self.current_arc_index = selected_index + 1
        self._refresh_arcs_preview()

    def _duplicate_selected_arc(self):
        selected_index = self._get_selected_arc_index()
        if selected_index is None:
            return
        duplicated_arc = dict(self.arcs[selected_index])
        self.arcs.insert(selected_index + 1, duplicated_arc)
        self.current_arc_index = selected_index + 1
        self._refresh_arcs_preview()

    def _delete_selected_arc(self):
        selected_index = self._get_selected_arc_index()
        if selected_index is None:
            return
        self.arcs.pop(selected_index)
        if not self.arcs:
            self.current_arc_index = None
        else:
            self.current_arc_index = min(selected_index, len(self.arcs) - 1)
        self._refresh_arcs_preview()

    def _generate_arcs_from_scenarios(self):
        if not self.scenario_titles:
            messagebox.showwarning("No scenarios", "Load or create scenarios before generating arcs.", parent=self)
            return

        try:
            service = ArcGenerationService(self._get_ai(), self.scenario_wrapper)
            result = service.generate_arcs(self._build_arc_generation_foundation())
        except Exception as exc:
            messagebox.showerror("Arc generation failed", f"Unable to generate arcs: {exc}", parent=self)
            return

        generated_arcs = [dict(arc) for arc in (result.get("arcs") or []) if isinstance(arc, dict)]
        if not generated_arcs:
            messagebox.showwarning("No arcs", "The AI did not return any usable arcs.", parent=self)
            return

        action = self._confirm_generated_arc_action(len(generated_arcs))
        if action == "cancel":
            return

        self._apply_generated_arcs(generated_arcs, merge=(action == "merge"))
        messagebox.showinfo("Arcs generated", f"Applied {len(generated_arcs)} AI-generated arc(s).", parent=self)

    def _build_arc_generation_foundation(self) -> dict:
        return {
            "name": self.form_vars["name"].get().strip(),
            "genre": self.form_vars["genre"].get().strip(),
            "tone": self.form_vars["tone"].get().strip(),
            "status": self.form_vars["status"].get().strip(),
            "logline": self.logline_box.get("1.0", "end").strip(),
            "setting": self.setting_box.get("1.0", "end").strip(),
            "main_objective": self.objective_box.get("1.0", "end").strip(),
            "stakes": self.stakes_box.get("1.0", "end").strip(),
            "themes": [line.strip() for line in self.themes_box.get("1.0", "end").splitlines() if line.strip()],
            "notes": self.notes_box.get("1.0", "end").strip(),
            "existing_entities": load_existing_entity_catalog(
                ("villains", "factions", "places", "npcs", "creatures")
            ),
        }

    def _generate_scenarios_per_arc(self, *, existing_scenarios: list[dict] | None = None):
        try:
            self._validate_arcs_for_scenario_generation()
        except ArcScenarioExpansionValidationError as exc:
            messagebox.showwarning("Arc validation failed", str(exc), parent=self)
            return

        try:
            service = ArcScenarioExpansionService(self._get_ai())
            generated_payload = service.generate_scenarios(
                self._build_arc_generation_foundation(),
                self.arcs,
                existing_scenarios=existing_scenarios,
            )
        except Exception as exc:
            messagebox.showerror("Scenario generation failed", f"Unable to generate scenarios: {exc}", parent=self)
            return

        accepted_payload = self._preview_generated_arc_scenarios(generated_payload)
        if not accepted_payload:
            return

        persistence = CampaignForgePersistence(self.scenario_wrapper)
        dry_run = persistence.build_dry_run_report(
            accepted_payload,
            self.arcs,
            save_mode=SAVE_MODE_MERGE_KEEP_EXISTING,
        )
        if not self._confirm_campaign_forge_dry_run(dry_run, title="Scenario save preview"):
            return

        try:
            save_result = persistence.save_from_dry_run(accepted_payload, self.arcs, dry_run)
            saved_groups = save_result.get("saved_groups") or []
        except CampaignForgePersistenceError as exc:
            self._last_unsaved_generated_payload = persistence.unsaved_generated_payload
            messagebox.showerror("Scenario save failed", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Scenario save failed", f"Unable to save generated scenarios: {exc}", parent=self)
            return

        self._refresh_scenario_titles_from_saved_groups(saved_groups)
        self._refresh_arcs_preview()
        self._refresh_review()
        saved_count = sum(len(group.get("scenarios") or []) for group in saved_groups)
        messagebox.showinfo(
            "Scenarios generated",
            f"Saved {saved_count} generated scenario(s) across {len(saved_groups)} arc(s).",
            parent=self,
        )

    def _generate_db_aware_scenarios_per_arc(self):
        """Explicit user action for DB-aware scene generation and validation."""
        try:
            existing_scenarios = self.scenario_wrapper.load_items() if self.scenario_wrapper else []
        except Exception:
            existing_scenarios = []
        self._generate_scenarios_per_arc(existing_scenarios=existing_scenarios)

    def _forge_full_campaign(self):
        stages = [
            "1. Generate/normalize arcs",
            "2. Generate scenarios for each arc",
            "3. Validate and enrich scenes/entities",
            "4. Preview summary",
            "5. Save campaign + scenarios",
        ]
        progress_dialog = self._create_pipeline_progress_dialog("Forging full campaign...", stages)
        saved_groups: list[dict] = []
        pipeline_started = time.perf_counter()
        self._log_forge_event(
            "campaign_forge.ui.pipeline.start",
            "pipeline_started",
            arc_count=len(self.arcs),
            scenario_title_count=len(self.scenario_titles),
        )
        try:
            self._set_interactive_controls_enabled(False)
            stage_started = time.perf_counter()
            self._update_pipeline_progress(progress_dialog, 0, "Arcs")
            self._log_forge_event("campaign_forge.ui.stage.start", "arcs_started", stage="arcs")
            self._forge_pipeline_generate_or_normalize_arcs()
            self._log_forge_event(
                "campaign_forge.ui.stage.end",
                "arcs_completed",
                stage="arcs",
                elapsed_ms=self._elapsed_ms(stage_started),
                arc_count=len(self.arcs),
            )

            stage_started = time.perf_counter()
            self._update_pipeline_progress(progress_dialog, 1, "Scenarios")
            self._log_forge_event("campaign_forge.ui.stage.start", "scenario_generation_started", stage="scenarios")
            self._validate_arcs_for_scenario_generation()
            existing_scenarios = self._load_existing_scenarios_for_pipeline()
            service = ArcScenarioExpansionService(self._get_ai())
            generated_payload = service.generate_scenarios(
                self._build_arc_generation_foundation(),
                self.arcs,
                existing_scenarios=existing_scenarios,
            )
            generated_counts = self._summarize_generated_counts(generated_payload)
            self._log_forge_event(
                "campaign_forge.ui.stage.end",
                "scenario_generation_completed",
                stage="scenarios",
                elapsed_ms=self._elapsed_ms(stage_started),
                existing_scenario_count=len(existing_scenarios),
                generated_arc_count=generated_counts["arc_count"],
                generated_scenario_count=generated_counts["scenario_count"],
                generated_scene_count=generated_counts["scene_count"],
            )

            self._update_pipeline_progress(progress_dialog, 2, "Validation")
            self._log_forge_event(
                "campaign_forge.ui.stage.end",
                "validation_completed",
                stage="validation",
                generated_arc_count=generated_counts["arc_count"],
                generated_scenario_count=generated_counts["scenario_count"],
                generated_scene_count=generated_counts["scene_count"],
            )
            self._update_pipeline_progress(progress_dialog, 3, "Preview")
            accepted_payload = self._preview_generated_arc_scenarios(generated_payload)
            if not accepted_payload:
                self._log_forge_event(
                    "campaign_forge.ui.stage.warning",
                    "preview_cancelled",
                    level="warning",
                    stage="preview",
                )
                messagebox.showinfo("Forge cancelled", "Campaign forging cancelled during preview.", parent=self)
                return

            stage_started = time.perf_counter()
            self._update_pipeline_progress(progress_dialog, 4, "Saving")
            self._log_forge_event("campaign_forge.ui.stage.start", "save_started", stage="save")
            persistence = CampaignForgePersistence(
                self.scenario_wrapper,
                campaign_wrapper=self.campaign_wrapper,
            )
            payload = self._build_campaign_save_payload()
            dry_run = persistence.build_dry_run_report(
                accepted_payload,
                self.arcs,
                save_mode=SAVE_MODE_REPLACE_GENERATED_ONLY,
            )
            if not self._confirm_campaign_forge_dry_run(dry_run, title="Forge save preview"):
                self._log_forge_event(
                    "campaign_forge.ui.stage.warning",
                    "save_preview_cancelled",
                    level="warning",
                    stage="save",
                )
                messagebox.showinfo("Forge cancelled", "Campaign forging cancelled during save preview.", parent=self)
                return

            save_result = persistence.save_from_dry_run(
                accepted_payload,
                self.arcs,
                dry_run,
                campaign_metadata=payload,
                campaign_original_key=self.original_campaign_name,
            )
            saved_groups = save_result.get("saved_groups") or []
            self._refresh_scenario_titles_from_saved_groups(saved_groups)
            self.original_campaign_name = payload.get("Name")
            self._refresh_arcs_preview()
            self._refresh_review()
            saved_count = sum(len(group.get("scenarios") or []) for group in saved_groups)
            self._log_forge_event(
                "campaign_forge.ui.stage.end",
                "save_completed",
                stage="save",
                elapsed_ms=self._elapsed_ms(stage_started),
                saved_group_count=len(saved_groups),
                saved_scenario_count=saved_count,
            )
        except ArcScenarioExpansionValidationError as exc:
            self._log_forge_event(
                "campaign_forge.ui.pipeline.validation_error",
                "pipeline_validation_error",
                level="warning",
                error_type=type(exc).__name__,
                detail=str(exc),
                elapsed_ms=self._elapsed_ms(pipeline_started),
            )
            messagebox.showwarning("Pipeline validation failed", str(exc), parent=self)
            return
        except Exception as exc:
            self._log_forge_event(
                "campaign_forge.ui.pipeline.error",
                "pipeline_failed",
                level="error",
                error_type=type(exc).__name__,
                detail=str(exc),
                elapsed_ms=self._elapsed_ms(pipeline_started),
            )
            messagebox.showerror("Forge failed", f"Unable to forge full campaign: {exc}", parent=self)
            return
        finally:
            self._set_interactive_controls_enabled(True)
            if progress_dialog["window"].winfo_exists():
                progress_dialog["window"].destroy()

        saved_count = sum(len(group.get("scenarios") or []) for group in saved_groups)
        self._log_forge_event(
            "campaign_forge.ui.pipeline.completed",
            "pipeline_completed",
            elapsed_ms=self._elapsed_ms(pipeline_started),
            arc_count=len(self.arcs),
            saved_group_count=len(saved_groups),
            saved_scenario_count=saved_count,
        )
        messagebox.showinfo(
            "Campaign forged",
            f"Saved campaign '{self.form_vars['name'].get().strip()}' and {saved_count} generated scenario(s).",
            parent=self,
        )

    def _load_existing_scenarios_for_pipeline(self) -> list[dict]:
        try:
            return self.scenario_wrapper.load_items() if self.scenario_wrapper else []
        except Exception:
            return []

    def _forge_pipeline_generate_or_normalize_arcs(self):
        if self.arcs:
            self.arcs = [self._normalize_arc_dict(arc) for arc in self.arcs if (arc.get("name") or "").strip()]
            self.current_arc_index = 0 if self.arcs else None
            self._refresh_arcs_preview()
            if self.arcs:
                return

        if not self.scenario_titles:
            raise ArcScenarioExpansionValidationError(
                "No scenarios available to generate arcs. Add scenarios or create arcs manually first."
            )

        service = ArcGenerationService(self._get_ai(), self.scenario_wrapper)
        result = service.generate_arcs(self._build_arc_generation_foundation())
        generated_arcs = [dict(arc) for arc in (result.get("arcs") or []) if isinstance(arc, dict)]
        if not generated_arcs:
            raise ArcScenarioExpansionValidationError("The AI did not return usable arcs for this campaign.")
        self._apply_generated_arcs(generated_arcs, merge=False)

    def _build_campaign_save_payload(self) -> dict:
        return build_campaign_payload(
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


    def _confirm_campaign_forge_dry_run(self, dry_run: dict, *, title: str) -> bool:
        scenarios_summary = dry_run.get("scenarios", {}).get("summary", {})
        arc_summary = dry_run.get("arc_linkage", {}).get("summary", {})
        message = (
            "Review before saving:\n\n"
            f"Scenarios: {int(scenarios_summary.get('new', 0))} new, "
            f"{int(scenarios_summary.get('updated', 0))} updated, "
            f"{int(scenarios_summary.get('skipped', 0))} skipped.\n"
            f"Arc links updated: {int(arc_summary.get('updated', 0))}."
        )
        return messagebox.askyesno(title, message, parent=self)

    def _create_pipeline_progress_dialog(self, title: str, stages: list[str]):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Campaign Forge Progress")
        dialog.geometry("560x320")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        position_window_at_top(dialog)

        ctk.CTkLabel(dialog, text=title, font=("Arial", 16, "bold"), text_color=EDITOR_PALETTE["text"]).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        stage_var = ctk.StringVar(value="Preparing...")
        ctk.CTkLabel(dialog, textvariable=stage_var, text_color=EDITOR_PALETTE["muted_text"]).pack(
            anchor="w", padx=16, pady=(0, 8)
        )
        progress_bar = ctk.CTkProgressBar(dialog, height=16)
        progress_bar.pack(fill="x", padx=16, pady=(0, 12))
        progress_bar.set(0)

        stage_list = ctk.CTkTextbox(dialog, height=180, fg_color=EDITOR_PALETTE["surface_soft"])
        stage_list.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        stage_list.insert("1.0", "\n".join(f"○ {stage}" for stage in stages))
        stage_list.configure(state="disabled")
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        self.update_idletasks()
        return {
            "window": dialog,
            "stage_var": stage_var,
            "progress_bar": progress_bar,
            "stage_list": stage_list,
            "stages": stages,
        }

    def _update_pipeline_progress(self, progress_dialog: dict, stage_index: int, message: str):
        progress_dialog["stage_var"].set(message)
        total_stages = max(1, len(progress_dialog["stages"]))
        progress_dialog["progress_bar"].set((stage_index + 1) / total_stages)
        stage_lines = []
        for idx, label in enumerate(progress_dialog["stages"]):
            if idx < stage_index:
                prefix = "✓"
            elif idx == stage_index:
                prefix = "▶"
            else:
                prefix = "○"
            stage_lines.append(f"{prefix} {label}")
        stage_box = progress_dialog["stage_list"]
        stage_box.configure(state="normal")
        stage_box.delete("1.0", "end")
        stage_box.insert("1.0", "\n".join(stage_lines))
        stage_box.configure(state="disabled")
        self.update()

    def _log_forge_event(self, event: str, action: str, *, level: str = "info", **details):
        detail_parts = [f"{key}={details[key]!r}" for key in sorted(details.keys())]
        message = f"event={event} action={action}"
        if detail_parts:
            message = f"{message} {' '.join(detail_parts)}"

        if level == "error":
            log_error(message, func_name="campaign_forge.wizard")
            return
        if level == "warning":
            log_warning(message, func_name="campaign_forge.wizard")
            return
        log_info(message, func_name="campaign_forge.wizard")

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, int((time.perf_counter() - started_at) * 1000))

    @staticmethod
    def _summarize_generated_counts(payload: dict) -> dict[str, int]:
        arc_groups = [item for item in (payload.get("arcs") or []) if isinstance(item, dict)]
        scenario_count = 0
        scene_count = 0
        for group in arc_groups:
            scenarios = [item for item in (group.get("scenarios") or []) if isinstance(item, dict)]
            scenario_count += len(scenarios)
            for scenario in scenarios:
                scenes = scenario.get("scene_ideas") or scenario.get("scenes") or []
                if isinstance(scenes, list):
                    scene_count += len([scene for scene in scenes if isinstance(scene, dict)])
        return {
            "arc_count": len(arc_groups),
            "scenario_count": scenario_count,
            "scene_count": scene_count,
        }

    def _register_interactive_control(self, *widgets):
        for widget in widgets:
            if widget and widget not in self._interactive_controls:
                self._interactive_controls.append(widget)

    def _set_interactive_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget in self._interactive_controls:
            if widget.winfo_exists():
                widget.configure(state=state)

    def _validate_arcs_for_scenario_generation(self):
        if not self.arcs:
            raise ArcScenarioExpansionValidationError("Add at least one arc before generating scenarios.")

        for arc in self.arcs:
            error_message = ArcEditorDialog.validate_generation_requirements(arc)
            if error_message:
                raise ArcScenarioExpansionValidationError(error_message)

    def _preview_generated_arc_scenarios(self, generated_payload: dict) -> dict | None:
        arc_metadata_by_name = {
            str(arc.get("name") or "").strip().casefold(): arc for arc in self.arcs if isinstance(arc, dict)
        }
        return preview_campaign_forge_payload(
            self,
            campaign_summary=self._build_campaign_forge_summary(),
            generated_payload=generated_payload,
            arc_metadata_by_name=arc_metadata_by_name,
        )

    def _build_campaign_forge_summary(self) -> str:
        name = self.form_vars["name"].get().strip() if hasattr(self, "form_vars") else ""
        genre = self.form_vars["genre"].get().strip() if hasattr(self, "form_vars") else ""
        tone = self.form_vars["tone"].get().strip() if hasattr(self, "form_vars") else ""
        main_objective = self.objective_box.get("1.0", "end").strip() if hasattr(self, "objective_box") else ""
        stakes = self.stakes_box.get("1.0", "end").strip() if hasattr(self, "stakes_box") else ""
        arc_count = len(self.arcs)
        summary_bits = [
            f"Name: {name or 'Unnamed campaign'}",
            f"Genre: {genre or '—'}",
            f"Tone: {tone or '—'}",
            f"Main objective: {main_objective or '—'}",
            f"Stakes: {stakes or '—'}",
            f"Current arc cards: {arc_count}",
        ]
        return "\n".join(summary_bits)

    def _confirm_generated_arc_action(self, generated_count: int) -> str:
        if not self.arcs:
            return "replace"

        replace_existing = messagebox.askyesnocancel(
            "Apply generated arcs",
            f"The AI generated {generated_count} arc(s).\n\nYes = replace current arcs\nNo = merge with current arcs\nCancel = keep current arcs",
            parent=self,
        )
        if replace_existing is None:
            return "cancel"
        return "replace" if replace_existing else "merge"

    def _apply_generated_arcs(self, generated_arcs: list[dict], merge: bool = False):
        normalized_generated = [self._normalize_arc_dict(arc) for arc in generated_arcs if arc.get("name")]
        if merge:
            self.arcs = self._merge_arcs(self.arcs, normalized_generated)
        else:
            self.arcs = normalized_generated
        self.current_arc_index = 0 if self.arcs else None
        self._refresh_arcs_preview()
        self._refresh_review()

    def _merge_arcs(self, existing_arcs: list[dict], generated_arcs: list[dict]) -> list[dict]:
        merged = [self._normalize_arc_dict(arc) for arc in existing_arcs if arc.get("name")]
        existing_names = {arc["name"].casefold() for arc in merged}
        for arc in generated_arcs:
            normalized = self._normalize_arc_dict(arc)
            if normalized["name"].casefold() in existing_names:
                continue
            merged.append(normalized)
            existing_names.add(normalized["name"].casefold())
        return merged

    @staticmethod
    def _normalize_arc_dict(arc: dict) -> dict:
        return {
            "name": (arc.get("name") or "").strip(),
            "summary": (arc.get("summary") or "").strip(),
            "objective": (arc.get("objective") or "").strip(),
            "status": canonicalize_arc_status(arc.get("status")),
            "thread": (arc.get("thread") or "").strip(),
            "scenarios": [str(title).strip() for title in (arc.get("scenarios") or []) if str(title).strip()],
        }

    def _get_ai(self):
        if self._ai_client is None:
            from modules.ai.local_ai_client import LocalAIClient

            self._ai_client = LocalAIClient()
        return self._ai_client

    def _get_selected_arc_index(self) -> int | None:
        if not self.arcs:
            return None
        if self.current_arc_index is None:
            self.current_arc_index = 0
        if self.current_arc_index < 0 or self.current_arc_index >= len(self.arcs):
            self.current_arc_index = len(self.arcs) - 1
        return self.current_arc_index

    @staticmethod
    def _extract_arc_index_from_preview_line(line_text: str) -> int | None:
        match = re.match(r"\s*Order\s+(\d+):", line_text or "")
        if not match:
            return None
        try:
            return max(0, int(match.group(1)) - 1)
        except ValueError:
            return None

    def _on_arcs_preview_click(self, event):
        selected_index = self._select_arc_from_preview_event(event)
        if selected_index is None:
            return "break"
        return "break"

    def _on_arcs_preview_double_click(self, event):
        selected_index = self._select_arc_from_preview_event(event)
        if selected_index is None:
            return "break"
        self._edit_selected_arc()
        return "break"

    def _select_arc_from_preview_event(self, event) -> int | None:
        if not self.arcs:
            return None

        self.arcs_list.configure(state="normal")
        try:
            line_index = int(self.arcs_list.index(f"@{event.x},{event.y}").split(".")[0])
        finally:
            self.arcs_list.configure(state="disabled")

        selected_index = self._find_arc_index_for_line(line_index)
        if selected_index is None:
            return None

        self.current_arc_index = min(selected_index, len(self.arcs) - 1)
        self._refresh_arcs_preview()
        return self.current_arc_index

    def _refresh_arcs_preview(self):
        if not self.arcs:
            self.current_arc_index = None
        elif self.current_arc_index is None:
            self.current_arc_index = 0
        else:
            self.current_arc_index = max(0, min(self.current_arc_index, len(self.arcs) - 1))

        self.arcs_list.configure(state="normal")
        self.arcs_list.delete("1.0", "end")
        self.arcs_list.tag_delete("arc_selected")
        self._arc_line_ranges = []

        try:
            self.arcs_list.tag_config(
                "arc_selected",
                background=EDITOR_PALETTE["accent"],
                foreground="#FFFFFF",
            )
        except Exception:
            # Some Tk themes can reject tag-level color overrides.
            pass

        if not self.arcs:
            self.arcs_list.insert("end", "No arc yet. Add one to structure your campaign progression.")
        for idx, arc in enumerate(self.arcs, start=1):
            block_start_line = int(float(self.arcs_list.index("end-1c")))
            self.arcs_list.insert("end", f"Order {idx}: {arc.get('name')} [{arc.get('status', 'Planned')}]\n")
            self.arcs_list.insert("end", f"   Objective: {arc.get('objective', '')}\n")
            self.arcs_list.insert("end", f"   Thread: {arc.get('thread', '') or '—'}\n")
            self.arcs_list.insert("end", f"   Scenarios: {', '.join(arc.get('scenarios') or [])}\n\n")
            block_end_line = max(block_start_line, int(float(self.arcs_list.index("end-1c"))) - 1)
            self._arc_line_ranges.append((block_start_line, block_end_line, idx - 1))

            if self.current_arc_index == idx - 1:
                self.arcs_list.tag_add("arc_selected", f"{block_start_line}.0", f"{block_end_line}.end")
        self.arcs_list.configure(state="disabled")

    def _find_arc_index_for_line(self, line_index: int) -> int | None:
        for start_line, end_line, arc_index in self._arc_line_ranges:
            if start_line <= line_index <= end_line:
                return arc_index
        return None

    def _refresh_review(self):
        if not hasattr(self, "review_box"):
            return

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
            payload = self._build_campaign_save_payload()
            self.campaign_wrapper.save_item(
                payload,
                key_field="Name",
                original_key_value=self.original_campaign_name,
            )
        except Exception as exc:
            messagebox.showerror("Save failed", f"Unable to save campaign: {exc}", parent=self)
            return

        messagebox.showinfo("Campaign saved", f"Campaign '{payload['Name']}' has been saved.", parent=self)
        self.destroy()


    def _load_existing_campaign(self):
        campaign_payload = self._choose_existing_campaign()
        if not campaign_payload:
            return

        self._apply_campaign_to_form(campaign_payload)
        self.original_campaign_name = str(campaign_payload.get("Name") or "").strip() or None
        self._refresh_arcs_preview()
        self._refresh_review()
        self._show_step(0)

    def _choose_existing_campaign(self):
        try:
            template = load_template("campaigns")
        except Exception as exc:
            log_exception(
                f"Failed to load campaign template: {exc}",
                func_name="CampaignBuilderWizard._choose_existing_campaign",
            )
            messagebox.showerror("Template Error", "Unable to load the campaign list.", parent=self)
            return None

        result = {"payload": None}
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Campaign")
        dialog.geometry("1100x1040")
        dialog.minsize(1100, 1040)

        view = GenericListSelectionView(
            dialog,
            "campaigns",
            self.campaign_wrapper,
            template,
            on_select_callback=lambda _et, _name, item=None, win=dialog: (
                result.__setitem__("payload", dict(item) if isinstance(item, dict) else None),
                win.destroy(),
            ),
        )
        view.pack(fill="both", expand=True)
        dialog.transient(self)
        dialog.grab_set()
        position_window_at_top(dialog)
        self.wait_window(dialog)
        return result["payload"]

    def _apply_campaign_to_form(self, campaign_data: dict):
        form_data, text_areas, arcs = build_form_state_from_campaign(campaign_data)

        for key in ("name", "genre", "tone", "status"):
            self.form_vars[key].set(form_data.get(key, ""))

        self.start_date_field.set(form_data.get("start_date", ""))
        self.end_date_field.set(form_data.get("end_date", ""))

        self._set_textbox_value(self.logline_box, text_areas.get("logline", ""))
        self._set_textbox_value(self.setting_box, text_areas.get("setting", ""))
        self._set_textbox_value(self.objective_box, text_areas.get("main_objective", ""))
        self._set_textbox_value(self.stakes_box, text_areas.get("stakes", ""))
        self._set_textbox_value(self.themes_box, text_areas.get("themes", ""))
        self._set_textbox_value(self.notes_box, text_areas.get("notes", ""))

        self.arcs = arcs
        self.current_arc_index = 0 if self.arcs else None
        self.selected_preset_id = None
        self._restore_selected_preset_label()
        self._refresh_preset_description()

    @staticmethod
    def _set_textbox_value(textbox: ctk.CTkTextbox, value: str):
        textbox.delete("1.0", "end")
        textbox.insert("1.0", value or "")

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

    def _refresh_scenario_titles_from_saved_groups(self, saved_groups: list[dict]) -> None:
        for group in saved_groups:
            for scenario in group.get("scenarios") or []:
                title = str(scenario.get("Title") or "").strip()
                if title and title not in self.scenario_titles:
                    self.scenario_titles.append(title)
