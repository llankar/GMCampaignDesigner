from __future__ import annotations

import json
import customtkinter as ctk
from tkinter import messagebox

from modules.campaigns.services import (
    build_campaign_payload,
    build_form_state_from_campaign,
    list_campaign_presets,
)
from modules.campaigns.ui.arc_editor_dialog import ArcEditorDialog
from modules.campaigns.ui.widgets import CampaignDateField
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.logging_helper import log_exception
from modules.helpers.template_loader import load_template
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
        self.geometry("980x1040")
        self.configure(fg_color=EDITOR_PALETTE["surface"])

        self.campaign_wrapper = campaign_wrapper
        self.scenario_titles = self._load_scenario_titles(scenario_wrapper)
        self.available_presets = list_campaign_presets()
        self.preset_by_id = {preset["id"]: preset for preset in self.available_presets}
        self.selected_preset_id: str | None = None

        self.arcs: list[dict] = []
        self.current_arc_index: int | None = None
        self.original_campaign_name: str | None = None
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

        load_row = ctk.CTkFrame(root, fg_color="transparent")
        load_row.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            load_row,
            text="Load Existing Campaign",
            command=self._load_existing_campaign,
            **primary_button_style(),
        ).pack(side="left")

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
        self.arcs_list.configure(state="disabled")

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 12), padx=12)
        self.arc_selection_var = ctk.StringVar(value="No arc selected")
        self.arc_selection_menu = ctk.CTkOptionMenu(
            buttons,
            variable=self.arc_selection_var,
            values=["No arc selected"],
            command=self._on_arc_selection_change,
            **option_menu_style(),
        )
        self.arc_selection_menu.pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Add Arc", command=self._add_arc, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Edit Arc", command=self._edit_selected_arc, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Move Up", command=self._move_arc_up, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Move Down", command=self._move_arc_down, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Duplicate", command=self._duplicate_selected_arc, **primary_button_style()).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Delete", command=self._delete_selected_arc, **primary_button_style()).pack(side="left", padx=4)

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

    def _get_selected_arc_index(self) -> int | None:
        if not self.arcs:
            return None
        if self.current_arc_index is None:
            self.current_arc_index = 0
        if self.current_arc_index < 0 or self.current_arc_index >= len(self.arcs):
            self.current_arc_index = len(self.arcs) - 1
        return self.current_arc_index

    def _on_arc_selection_change(self, value: str):
        if not value.startswith("#"):
            self.current_arc_index = None
            return
        try:
            index_str = value.split(" ", 1)[0].lstrip("#")
            self.current_arc_index = int(index_str) - 1
        except (TypeError, ValueError):
            self.current_arc_index = None

    def _refresh_arc_selection(self):
        if not self.arcs:
            self.arc_selection_menu.configure(values=["No arc selected"])
            self.arc_selection_var.set("No arc selected")
            self.current_arc_index = None
            return

        options = [f"#{idx}. {arc.get('name') or 'Untitled Arc'}" for idx, arc in enumerate(self.arcs, start=1)]
        self.arc_selection_menu.configure(values=options)

        if self.current_arc_index is None:
            self.current_arc_index = 0
        self.current_arc_index = max(0, min(self.current_arc_index, len(self.arcs) - 1))
        self.arc_selection_var.set(options[self.current_arc_index])

    def _refresh_arcs_preview(self):
        self._refresh_arc_selection()
        self.arcs_list.configure(state="normal")
        self.arcs_list.delete("1.0", "end")
        if not self.arcs:
            self.arcs_list.insert("end", "No arc yet. Add one to structure your campaign progression.")
        for idx, arc in enumerate(self.arcs, start=1):
            selected_marker = " <- selected" if self.current_arc_index == idx - 1 else ""
            self.arcs_list.insert("end", f"Order {idx}: {arc.get('name')} [{arc.get('status', 'Planned')}]" + selected_marker + "\n")
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
