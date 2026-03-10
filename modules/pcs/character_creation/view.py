"""UI for Savage Fate character creation flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .constants import SKILLS
from .equipment import available_equipment_points, max_pe_per_object
from .exporters import export_character_sheet
from .points import summarize_point_budgets
from .progression import ADVANCEMENT_OPTIONS, BASE_FEAT_COUNT, BASE_PROWESS_POINTS, prowess_points_from_advancement_choices
from .progression.rank_limits import bonus_skill_points_from_advancements, max_favorite_skills
from .rules_engine import CharacterCreationError, build_character
from .storage import CharacterDraftRepository
from .ui import EquipmentEditor, ProwessEditor, bind_advancement_type_and_label_vars
from .storage.payload_normalizer import normalize_draft_payload_for_form


class CharacterCreationView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.drafts = CharacterDraftRepository()
        self.advancement_rows = []
        self._advancement_choices_cache: list[dict[str, str]] = []
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="Character Creation (Savage Fate)", font=("Arial", 20, "bold"))
        title.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        scroll.grid_columnconfigure((0, 1), weight=1)

        self.inputs = {}
        self._entry(scroll, "Name", "name", 0, 0)
        self._entry(scroll, "Player", "player", 0, 1)
        self._entry(scroll, "Concept", "concept", 1, 0)
        self._entry(scroll, "Flaw", "flaw", 1, 1)
        self._entry(scroll, "Group asset", "group_asset", 2, 0)
        self._entry(scroll, "Advancements", "advancements", 2, 1, default="0")
        self.inputs["advancements"].trace_add("write", self._on_advancements_changed)

        draft_row = ctk.CTkFrame(scroll)
        draft_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))
        draft_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(draft_row, text="Saved character").grid(row=0, column=0, sticky="w", padx=(6, 4))
        self.draft_name_var = tk.StringVar(value="")
        self.draft_selector = ctk.CTkComboBox(draft_row, variable=self.draft_name_var, values=[], state="readonly")
        self.draft_selector.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(draft_row, text="Load", width=90, command=self._load_selected_draft).grid(
            row=0, column=2, padx=4
        )
        ctk.CTkButton(draft_row, text="Save", width=110, command=self._save_current_draft).grid(
            row=0, column=3, padx=(4, 6)
        )

        self.advancement_frame = ctk.CTkFrame(scroll)
        self.advancement_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 4))
        self.advancement_frame.grid_columnconfigure(1, weight=1)

        self.favorite_vars = {}
        self.skill_vars = {}
        self.bonus_skill_vars = {}
        self.skills_header_var = tk.StringVar(value="Skills (15 base points, max favorites: 6)")
        ctk.CTkLabel(scroll, textvariable=self.skills_header_var, font=("Arial", 14, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(10, 2)
        )
        self.remaining_points_var = tk.StringVar(value="Base remaining: 15 | Bonus remaining: 0")
        ctk.CTkLabel(scroll, textvariable=self.remaining_points_var, font=("Arial", 12, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4)
        )
        skill_frame = ctk.CTkFrame(scroll)
        skill_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        for i, skill in enumerate(SKILLS):
            r = i // 2
            c = (i % 2) * 3
            ctk.CTkLabel(skill_frame, text=skill).grid(row=r, column=c, sticky="w", padx=(6, 2), pady=2)
            fav = tk.BooleanVar(value=i < 6)
            pts = tk.StringVar(value="0")
            bonus_pts = tk.StringVar(value="0")
            self.favorite_vars[skill] = fav
            self.skill_vars[skill] = pts
            self.bonus_skill_vars[skill] = bonus_pts
            ctk.CTkCheckBox(skill_frame, text="Fav", variable=fav, onvalue=True, offvalue=False).grid(row=r, column=c + 1)
            point_box = ctk.CTkFrame(skill_frame)
            point_box.grid(row=r, column=c + 2, padx=(2, 10), pady=1, sticky="w")
            ctk.CTkLabel(point_box, text="B", width=12).grid(row=0, column=0, padx=(2, 2))
            ctk.CTkEntry(point_box, textvariable=pts, width=40).grid(row=0, column=1, padx=(0, 4))
            ctk.CTkLabel(point_box, text="+", width=12).grid(row=0, column=2, padx=(0, 2))
            ctk.CTkLabel(point_box, text="Bo", width=18).grid(row=0, column=3, padx=(0, 2))
            ctk.CTkEntry(point_box, textvariable=bonus_pts, width=40).grid(row=0, column=4)
            fav.trace_add("write", self._update_remaining_points_marker)
            pts.trace_add("write", self._update_remaining_points_marker)
            bonus_pts.trace_add("write", self._update_remaining_points_marker)

        ctk.CTkLabel(scroll, text="Prowess", font=("Arial", 14, "bold")).grid(
            row=8, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self.feat_count_var = tk.StringVar(value=f"Prowess count: {BASE_FEAT_COUNT}")
        self.prowess_points_var = tk.StringVar(value=f"Prowess points (total/available): {BASE_PROWESS_POINTS}/{BASE_PROWESS_POINTS}")
        counters = ctk.CTkFrame(scroll)
        counters.grid(row=8, column=1, sticky="e", padx=6, pady=(10, 2))
        ctk.CTkLabel(counters, textvariable=self.feat_count_var, font=("Arial", 12, "bold")).grid(
            row=0, column=0, sticky="e"
        )
        ctk.CTkLabel(counters, textvariable=self.prowess_points_var, font=("Arial", 12, "bold")).grid(
            row=1, column=0, sticky="e"
        )
        self.extra_feat_count = 0
        ctk.CTkButton(scroll, text="+ Add prowess", width=170, command=self._add_feat_row).grid(
            row=9, column=1, sticky="e", padx=6, pady=(0, 4)
        )
        self.prowess_editor = ProwessEditor(
            scroll,
            on_change=self._update_prowess_points_marker,
            on_remove_feat=self._remove_feat_row,
            grid_row=10,
        )
        self._render_feat_rows([])

        ctk.CTkLabel(scroll, text="Equipment", font=("Arial", 14, "bold")).grid(
            row=11, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self.available_equipment_pe_var = tk.StringVar(value="Available EP: 3 | Cap per item: 1 | Remaining: 0")
        ctk.CTkLabel(scroll, textvariable=self.available_equipment_pe_var, font=("Arial", 12, "bold")).grid(
            row=11, column=1, sticky="e", padx=6, pady=(10, 2)
        )
        for key in ("weapon", "armor", "utility", "weapon_pe", "armor_pe", "utility_pe"):
            self.inputs[key] = tk.StringVar(value="")

        self.equipment_editor: EquipmentEditor | None = None
        self.equipment_editor = EquipmentEditor(
            scroll,
            on_change=self._update_equipment_points_marker,
            max_level_provider=lambda: max_pe_per_object(self._safe_int(self.inputs["advancements"].get())),
            grid_row=12,
        )

        self._update_favorites_limit_ui()
        self._update_remaining_points_marker()
        self._update_equipment_points_marker()
        self._refresh_draft_selector()
        self._render_advancement_rows()

        export_row = ctk.CTkFrame(self)
        export_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        export_row.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(export_row, text="Export: HTML").grid(row=0, column=0, padx=(0, 6), sticky="w")
        ctk.CTkLabel(export_row, text="Language").grid(row=0, column=1, padx=(0, 4), sticky="w")
        self.export_language_label_var = tk.StringVar(value="Français")
        self.export_language_selector = ctk.CTkComboBox(
            export_row,
            variable=self.export_language_label_var,
            values=["Français", "English"],
            state="readonly",
            width=120,
        )
        self.export_language_selector.grid(row=0, column=2, padx=(0, 8), sticky="w")

        btn = ctk.CTkButton(export_row, text="Export sheet", command=self.create_character_pdf)
        btn.grid(row=0, column=3, sticky="e", padx=(10, 0))

    def _entry(self, parent, label, key, row, col, default=""):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=col, sticky="ew", padx=6, pady=3)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=label).grid(row=0, column=0, sticky="w", padx=6, pady=(4, 2))
        var = tk.StringVar(value=default)
        self.inputs[key] = var
        ctk.CTkEntry(frame, textvariable=var).grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

    def _build_payload(self) -> dict:
        favorites = [skill for skill, var in self.favorite_vars.items() if var.get()]
        feats = self.prowess_editor.get_payload()
        advancement_choices = []
        for row in self.advancement_rows:
            advancement_choices.append(
                {
                    "type": row["type_var"].get().strip(),
                    "details": row["details_var"].get().strip(),
                }
            )
        return {
            "name": self.inputs["name"].get().strip(),
            "player": self.inputs["player"].get().strip(),
            "concept": self.inputs["concept"].get().strip(),
            "flaw": self.inputs["flaw"].get().strip(),
            "group_asset": self.inputs["group_asset"].get().strip(),
            "advancements": int(self.inputs["advancements"].get() or 0),
            "advancement_choices": advancement_choices,
            "favorites": favorites,
            "skills": {skill: int((var.get() or "0")) for skill, var in self.skill_vars.items()},
            "bonus_skills": {skill: int((var.get() or "0")) for skill, var in self.bonus_skill_vars.items()},
            "feats": feats,
            "equipment": self.equipment_editor.get_equipment_names(),
            "equipment_pe": self.equipment_editor.get_allocated_pe(),
            "equipment_purchases": self.equipment_editor.get_purchase_payload(),
        }

    def _on_advancements_changed(self, *_args):
        self._update_favorites_limit_ui()
        self._render_advancement_rows()
        self._render_feat_rows(self._collect_current_feats())
        self._update_remaining_points_marker()
        self._update_equipment_points_marker()

    def _update_favorites_limit_ui(self) -> None:
        advancement_count = self._safe_int(self.inputs["advancements"].get())
        favorite_limit = max_favorite_skills(advancement_count)
        self.skills_header_var.set(f"Skills (15 base points, max favorites: {favorite_limit})")

    def _render_advancement_rows(self):
        existing_choices = self._collect_cached_advancement_choices()

        for widget in self.advancement_frame.winfo_children():
            widget.destroy()
        self.advancement_rows = []

        advancement_count = self._safe_int(self.inputs["advancements"].get())
        if advancement_count <= 0:
            self._advancement_choices_cache = existing_choices
            return

        self._advancement_choices_cache = existing_choices[:advancement_count]

        # Headless tests may provide a lightweight placeholder instead of a real
        # Tk container. Preserve the data model without requiring widget creation.
        if not hasattr(self.advancement_frame, "tk"):
            for idx in range(advancement_count):
                existing_choice = self._advancement_choices_cache[idx] if idx < len(self._advancement_choices_cache) else {}
                initial_type = (existing_choice.get("type") or "").strip() or ADVANCEMENT_OPTIONS[0][0]
                option_var = tk.StringVar(value=initial_type)
                details_var = tk.StringVar(value=(existing_choice.get("details") or "").strip())
                self.advancement_rows.append(
                    {
                        "type_var": option_var,
                        "details_var": details_var,
                        "combo": None,
                        "label_map": {value: label for value, label in ADVANCEMENT_OPTIONS},
                        "label_var": None,
                    }
                )
            return

        ctk.CTkLabel(
            self.advancement_frame,
            text="Advancement choices",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 2))

        for idx in range(advancement_count):
            row_frame = ctk.CTkFrame(self.advancement_frame)
            row_frame.grid(row=idx + 1, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
            row_frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_frame, text=f"Advancement {idx + 1}").grid(row=0, column=0, sticky="w", padx=6, pady=4)

            existing_choice = self._advancement_choices_cache[idx] if idx < len(self._advancement_choices_cache) else {}
            initial_type = (existing_choice.get("type") or "").strip() or ADVANCEMENT_OPTIONS[0][0]
            option_var = tk.StringVar(value=initial_type)
            option_label_map = {value: label for value, label in ADVANCEMENT_OPTIONS}
            option_value_map = {label: value for value, label in ADVANCEMENT_OPTIONS}
            option_label_var = tk.StringVar(value=option_label_map.get(initial_type, ADVANCEMENT_OPTIONS[0][1]))

            bind_advancement_type_and_label_vars(
                type_var=option_var,
                label_var=option_label_var,
                label_to_value=option_value_map,
                value_to_label=option_label_map,
                on_type_updated=self._on_advancement_choice_updated,
            )

            choice = ctk.CTkComboBox(
                row_frame,
                variable=option_label_var,
                values=list(option_value_map.keys()),
                state="readonly",
            )
            choice.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

            details_var = tk.StringVar(value=(existing_choice.get("details") or "").strip())
            ctk.CTkEntry(row_frame, textvariable=details_var, placeholder_text="Narrative / mechanical details")\
                .grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))

            self.advancement_rows.append(
                {
                    "type_var": option_var,
                    "details_var": details_var,
                    "combo": choice,
                    "label_map": option_label_map,
                    "label_var": option_label_var,
                }
            )

    def _collect_cached_advancement_choices(self) -> list[dict[str, str]]:
        if not self.advancement_rows:
            return [
                {
                    "type": (choice.get("type") or "").strip(),
                    "details": (choice.get("details") or "").strip(),
                }
                for choice in self._advancement_choices_cache
            ]

        choices = [
            {
                "type": row["type_var"].get().strip(),
                "details": row["details_var"].get().strip(),
            }
            for row in self.advancement_rows
        ]
        self._advancement_choices_cache = choices
        return choices

    def _on_advancement_choice_updated(self, *_args):
        self._render_feat_rows(self._collect_current_feats())
        self._update_remaining_points_marker()
        self._update_equipment_points_marker()

    def _collect_current_feats(self) -> list[dict]:
        return self.prowess_editor.get_payload()

    def _render_feat_rows(self, existing_feats: list[dict]) -> None:
        advancement_choices = [
            {
                "type": row["type_var"].get().strip(),
                "details": row["details_var"].get().strip(),
            }
            for row in self.advancement_rows
        ]
        points_total = BASE_PROWESS_POINTS + sum(prowess_points_from_advancement_choices(advancement_choices))
        extra_feats = getattr(self, "extra_feat_count", 0)
        total_feats = BASE_FEAT_COUNT + extra_feats
        self.feat_count_var.set(f"Prowess count: {total_feats}")
        self.prowess_editor.set_feat_rows(total_feats, [], existing_feats)
        self._update_prowess_points_marker()

    def _update_prowess_points_marker(self) -> None:
        advancement_choices = [
            {
                "type": row["type_var"].get().strip(),
                "details": row["details_var"].get().strip(),
            }
            for row in self.advancement_rows
        ]
        points_total = BASE_PROWESS_POINTS + sum(prowess_points_from_advancement_choices(advancement_choices))
        points_spent = 0
        if hasattr(self, "prowess_editor") and hasattr(self.prowess_editor, "get_total_spent_prowess_points"):
            points_spent = self.prowess_editor.get_total_spent_prowess_points()
        points_available = points_total - points_spent
        if hasattr(self, "prowess_points_var"):
            self.prowess_points_var.set(f"Prowess points (total/available): {points_total}/{points_available}")

    def _add_feat_row(self) -> None:
        self.extra_feat_count += 1
        self._render_feat_rows(self._collect_current_feats())

    def _remove_feat_row(self, feat_index: int) -> None:
        feats = self._collect_current_feats()
        if not (0 <= feat_index < len(feats)):
            return
        if len(feats) <= 1:
            return

        feats.pop(feat_index)
        self.extra_feat_count = max(0, len(feats) - BASE_FEAT_COUNT)
        self._render_feat_rows(feats)

    def _refresh_draft_selector(self):
        names = self.drafts.list_names()
        self.draft_selector.configure(values=names or [""])
        if names:
            self.draft_selector.set(names[0])
            self.draft_name_var.set(names[0])
        else:
            self.draft_selector.set("")
            self.draft_name_var.set("")

    def _save_current_draft(self):
        try:
            payload = self._build_payload()
        except ValueError:
            messagebox.showerror("Character Creation", "Numeric fields are invalid.")
            return

        name = (payload.get("name") or "").strip()
        if not name:
            messagebox.showerror("Character Creation", "Character name is required to save.")
            return

        self.drafts.save(name, payload)
        self._refresh_draft_selector()
        self.draft_selector.set(name)
        self.draft_name_var.set(name)
        messagebox.showinfo("Character Creation", f"Character '{name}' saved in the current campaign.")

    def _load_selected_draft(self):
        name = (self.draft_name_var.get() or "").strip()
        if not name:
            messagebox.showerror("Character Creation", "Select a character to load.")
            return

        payload = self.drafts.load(name)
        if not payload:
            messagebox.showerror("Character Creation", f"Unable to load '{name}'.")
            return

        self._apply_payload(payload)
        messagebox.showinfo("Character Creation", f"Character '{name}' loaded.")

    def _apply_payload(self, payload: dict):
        normalized_payload = normalize_draft_payload_for_form(payload)

        for key, var in self.inputs.items():
            var.set(str(normalized_payload.get(key, "")))

        favorites = set(normalized_payload.get("favorites") or [])
        for skill, var in self.favorite_vars.items():
            var.set(skill in favorites)

        for skill, var in self.skill_vars.items():
            var.set(str((normalized_payload.get("skills") or {}).get(skill, 0)))

        for skill, var in self.bonus_skill_vars.items():
            var.set(str((normalized_payload.get("bonus_skills") or {}).get(skill, 0)))

        advancement_choices = normalized_payload.get("advancement_choices") or []
        self._render_advancement_rows()
        for idx, row in enumerate(self.advancement_rows):
            if idx >= len(advancement_choices):
                break
            entry = advancement_choices[idx] or {}
            choice_value = (entry.get("type") or "").strip() or ADVANCEMENT_OPTIONS[0][0]
            row["type_var"].set(choice_value)
            row["label_var"].set(row["label_map"].get(choice_value, ADVANCEMENT_OPTIONS[0][1]))
            row["details_var"].set((entry.get("details") or "").strip())

        loaded_feats = normalized_payload.get("feats") or []
        advancement_choices = normalized_payload.get("advancement_choices") or []
        dynamic_feat_count = BASE_FEAT_COUNT
        self.extra_feat_count = max(0, len(loaded_feats) - dynamic_feat_count)
        self._render_feat_rows(loaded_feats)

        self.equipment_editor.apply_payload(
            normalized_payload.get("equipment") or {},
            normalized_payload.get("equipment_purchases") or {},
        )

        self._update_remaining_points_marker()
        self._update_equipment_points_marker()

    def _update_equipment_points_marker(self, *_args) -> None:
        if self.equipment_editor is None:
            return

        advancement_choices = [
            {"type": row["type_var"].get().strip(), "details": row["details_var"].get().strip()}
            for row in self.advancement_rows
        ]
        available = available_equipment_points(advancement_choices)
        max_per_object = max_pe_per_object(self._safe_int(self.inputs["advancements"].get()))
        allocated_map = self.equipment_editor.get_allocated_pe()
        allocated = sum(allocated_map.values())
        for key, value in allocated_map.items():
            pe_key = f"{key}_pe"
            if pe_key in self.inputs:
                self.inputs[pe_key].set(str(value))
        for key, value in self.equipment_editor.get_equipment_names().items():
            if key in self.inputs:
                self.inputs[key].set(value)
        remaining = available - allocated
        self.available_equipment_pe_var.set(
            f"Available EP: {available} | Cap per item: {max_per_object} | Remaining: {remaining}"
        )

    def _safe_int(self, raw_value: str) -> int:
        try:
            return int((raw_value or "0").strip())
        except ValueError:
            return 0

    def _update_remaining_points_marker(self, *_args) -> None:
        base_points = {skill: self._safe_int(var.get()) for skill, var in self.skill_vars.items()}
        bonus_points = {skill: self._safe_int(var.get()) for skill, var in self.bonus_skill_vars.items()}
        favorites = [skill for skill, var in self.favorite_vars.items() if var.get()]
        favorite_limit = max_favorite_skills(self._safe_int(self.inputs["advancements"].get()))
        advancement_choices = []
        for row in self.advancement_rows:
            advancement_choices.append(
                {
                    "type": row["type_var"].get(),
                    "details": row["details_var"].get().strip(),
                }
            )
        summary = summarize_point_budgets(
            base_points,
            bonus_points,
            favorites,
            extra_generated_bonus=bonus_skill_points_from_advancements(advancement_choices),
        )
        self.remaining_points_var.set(
            f"Base remaining: {summary['remaining_base']} | "
            f"Bonus remaining: {summary['remaining_bonus']} | "
            f"Favorites: {len(favorites)}/{favorite_limit}"
        )

    def create_character_pdf(self):
        try:
            payload = self._build_payload()
            result = build_character(payload)
        except (ValueError, CharacterCreationError) as exc:
            messagebox.showerror("Character Creation", str(exc))
            return

        backend = "html"
        html_only = True

        extension = ".html"
        kind = "HTML"
        language = "fr" if self.export_language_label_var.get() == "Français" else "en"

        path = filedialog.asksaveasfilename(
            title="Export Savage Fate sheet",
            defaultextension=extension,
            filetypes=[(kind, f"*{extension}")],
            initialfile=f"{payload['name'].replace(' ', '_')}_character_sheet{extension}",
        )
        if not path:
            return

        try:
            out, used_backend = export_character_sheet(
                payload,
                result,
                path,
                backend=backend,
                export_html_only=html_only,
                language=language,
            )
        except Exception as exc:
            messagebox.showerror("Character Creation", f"Export failed:\n{exc}")
            return

        messagebox.showinfo("Character Creation", f"Sheet generated via backend '{used_backend}':\n{out}")
