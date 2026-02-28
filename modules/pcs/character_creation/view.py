"""UI for Savage Fate character creation flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .constants import SKILLS
from .exporters import export_character_sheet
from .points import summarize_point_budgets
from .progression import ADVANCEMENT_OPTIONS, BASE_FEAT_COUNT, prowess_points_from_advancement_choices
from .progression.rank_limits import bonus_skill_points_from_advancements, max_favorite_skills
from .rules_engine import CharacterCreationError, build_character
from .storage import CharacterDraftRepository
from .ui import bind_advancement_type_and_label_vars
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
        self._entry(scroll, "Nom", "name", 0, 0)
        self._entry(scroll, "Joueur", "player", 0, 1)
        self._entry(scroll, "Concept", "concept", 1, 0)
        self._entry(scroll, "Défaut", "flaw", 1, 1)
        self._entry(scroll, "Atout de groupe", "group_asset", 2, 0)
        self._entry(scroll, "Avancements", "advancements", 2, 1, default="0")
        self.inputs["advancements"].trace_add("write", self._on_advancements_changed)

        draft_row = ctk.CTkFrame(scroll)
        draft_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))
        draft_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(draft_row, text="Personnage sauvegardé").grid(row=0, column=0, sticky="w", padx=(6, 4))
        self.draft_name_var = tk.StringVar(value="")
        self.draft_selector = ctk.CTkComboBox(draft_row, variable=self.draft_name_var, values=[], state="readonly")
        self.draft_selector.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(draft_row, text="Charger", width=90, command=self._load_selected_draft).grid(
            row=0, column=2, padx=4
        )
        ctk.CTkButton(draft_row, text="Sauvegarder", width=110, command=self._save_current_draft).grid(
            row=0, column=3, padx=(4, 6)
        )

        self.advancement_frame = ctk.CTkFrame(scroll)
        self.advancement_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 4))
        self.advancement_frame.grid_columnconfigure(1, weight=1)

        self.favorite_vars = {}
        self.skill_vars = {}
        self.bonus_skill_vars = {}
        self.skills_header_var = tk.StringVar(value="Compétences (15 points de base, max favorites: 6)")
        ctk.CTkLabel(scroll, textvariable=self.skills_header_var, font=("Arial", 14, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(10, 2)
        )
        self.remaining_points_var = tk.StringVar(value="Base restants: 15 | Bonus restants: 0")
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

        ctk.CTkLabel(scroll, text="Prouesses", font=("Arial", 14, "bold")).grid(
            row=8, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self.feat_count_var = tk.StringVar(value=f"Nombre de prouesses: {BASE_FEAT_COUNT}")
        ctk.CTkLabel(scroll, textvariable=self.feat_count_var, font=("Arial", 12, "bold")).grid(
            row=8, column=1, sticky="e", padx=6, pady=(10, 2)
        )
        self.feat_frame = ctk.CTkFrame(scroll)
        self.feat_frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        self.feat_widgets = []
        self._render_feat_rows([])

        ctk.CTkLabel(scroll, text="Équipement", font=("Arial", 14, "bold")).grid(
            row=10, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self._entry(scroll, "Arme", "weapon", 11, 0)
        self._entry(scroll, "Armure", "armor", 11, 1)
        self._entry(scroll, "Utilitaire", "utility", 12, 0)
        self._entry(scroll, "PE Arme", "weapon_pe", 12, 1, default="1")
        self._entry(scroll, "PE Armure", "armor_pe", 13, 0, default="1")
        self._entry(scroll, "PE Utilitaire", "utility_pe", 13, 1, default="1")

        self._update_favorites_limit_ui()
        self._update_remaining_points_marker()
        self._refresh_draft_selector()
        self._render_advancement_rows()

        export_row = ctk.CTkFrame(self)
        export_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        export_row.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(export_row, text="Export: HTML").grid(row=0, column=0, padx=(0, 6), sticky="w")

        btn = ctk.CTkButton(export_row, text="Exporter fiche", command=self.create_character_pdf)
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
        feats = []
        for feat_widget in self.feat_widgets:
            feats.append(
                {
                    "name": feat_widget["name"].get().strip(),
                    "options": [
                        feat_widget["option_1"].get().strip(),
                        feat_widget["option_2"].get().strip(),
                        feat_widget["option_3"].get().strip(),
                    ],
                    "limitation": feat_widget["limitation"].get().strip(),
                    "prowess_points": feat_widget["prowess_points"],
                }
            )
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
            "equipment": {
                "weapon": self.inputs["weapon"].get().strip(),
                "armor": self.inputs["armor"].get().strip(),
                "utility": self.inputs["utility"].get().strip(),
            },
            "equipment_pe": {
                "weapon": int(self.inputs["weapon_pe"].get() or 0),
                "armor": int(self.inputs["armor_pe"].get() or 0),
                "utility": int(self.inputs["utility_pe"].get() or 0),
            },
        }

    def _on_advancements_changed(self, *_args):
        self._update_favorites_limit_ui()
        self._render_advancement_rows()
        self._render_feat_rows(self._collect_current_feats())
        self._update_remaining_points_marker()

    def _update_favorites_limit_ui(self) -> None:
        advancement_count = self._safe_int(self.inputs["advancements"].get())
        favorite_limit = max_favorite_skills(advancement_count)
        self.skills_header_var.set(f"Compétences (15 points de base, max favorites: {favorite_limit})")

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

        ctk.CTkLabel(
            self.advancement_frame,
            text="Choix des avancements",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 2))

        for idx in range(advancement_count):
            row_frame = ctk.CTkFrame(self.advancement_frame)
            row_frame.grid(row=idx + 1, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
            row_frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_frame, text=f"Avancement {idx + 1}").grid(row=0, column=0, sticky="w", padx=6, pady=4)

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
            ctk.CTkEntry(row_frame, textvariable=details_var, placeholder_text="Détails narratifs / mécaniques")\
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

    def _collect_current_feats(self) -> list[dict]:
        return [
            {
                "name": widget["name"].get().strip(),
                "options": [
                    widget["option_1"].get().strip(),
                    widget["option_2"].get().strip(),
                    widget["option_3"].get().strip(),
                ],
                "limitation": widget["limitation"].get().strip(),
            }
            for widget in self.feat_widgets
        ]

    def _render_feat_rows(self, existing_feats: list[dict]) -> None:
        for widget in self.feat_frame.winfo_children():
            widget.destroy()
        self.feat_widgets = []

        advancement_choices = [
            {
                "type": row["type_var"].get().strip(),
                "details": row["details_var"].get().strip(),
            }
            for row in self.advancement_rows
        ]
        prowess_budgets = prowess_points_from_advancement_choices(advancement_choices)
        total_feats = BASE_FEAT_COUNT + len(prowess_budgets)
        self.feat_count_var.set(f"Nombre de prouesses: {total_feats}")

        for idx in range(total_feats):
            feat = existing_feats[idx] if idx < len(existing_feats) else {}
            prowess_points = 0 if idx < BASE_FEAT_COUNT else prowess_budgets[idx - BASE_FEAT_COUNT]

            box = ctk.CTkFrame(self.feat_frame)
            box.grid(row=idx, column=0, columnspan=2, sticky="ew", pady=3)
            name = tk.StringVar(value=(feat.get("name") or f"Prouesse {idx + 1}").strip())
            options = feat.get("options") or []
            opt1 = tk.StringVar(value=options[0] if len(options) > 0 else "")
            opt2 = tk.StringVar(value=options[1] if len(options) > 1 else "")
            opt3 = tk.StringVar(value=options[2] if len(options) > 2 else "")
            lim = tk.StringVar(value=(feat.get("limitation") or "").strip())

            name_label = "Nom" if prowess_points <= 0 else f"Nom ({prowess_points} pt{'s' if prowess_points > 1 else ''} de prouesse)"
            for lbl, var, row in (
                (name_label, name, 0),
                ("Option 1", opt1, 1),
                ("Option 2", opt2, 2),
                ("Option 3", opt3, 3),
                ("Limitation", lim, 4),
            ):
                ctk.CTkLabel(box, text=lbl).grid(row=row, column=0, sticky="w", padx=6, pady=2)
                ctk.CTkEntry(box, textvariable=var).grid(row=row, column=1, sticky="ew", padx=6, pady=2)
            box.grid_columnconfigure(1, weight=1)
            self.feat_widgets.append(
                {
                    "name": name,
                    "option_1": opt1,
                    "option_2": opt2,
                    "option_3": opt3,
                    "limitation": lim,
                    "prowess_points": prowess_points,
                }
            )

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
            messagebox.showerror("Character Creation", "Les champs numériques sont invalides.")
            return

        name = (payload.get("name") or "").strip()
        if not name:
            messagebox.showerror("Character Creation", "Le nom du personnage est obligatoire pour sauvegarder.")
            return

        self.drafts.save(name, payload)
        self._refresh_draft_selector()
        self.draft_selector.set(name)
        self.draft_name_var.set(name)
        messagebox.showinfo("Character Creation", f"Personnage '{name}' sauvegardé dans la campagne courante.")

    def _load_selected_draft(self):
        name = (self.draft_name_var.get() or "").strip()
        if not name:
            messagebox.showerror("Character Creation", "Sélectionnez un personnage à charger.")
            return

        payload = self.drafts.load(name)
        if not payload:
            messagebox.showerror("Character Creation", f"Impossible de charger '{name}'.")
            return

        self._apply_payload(payload)
        messagebox.showinfo("Character Creation", f"Personnage '{name}' chargé.")

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

        self._render_feat_rows(normalized_payload.get("feats") or [])

        self._update_remaining_points_marker()

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
            f"Base restants: {summary['remaining_base']} | "
            f"Bonus restants: {summary['remaining_bonus']} | "
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
        path = filedialog.asksaveasfilename(
            title="Exporter la fiche Savage Fate",
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
            )
        except Exception as exc:
            messagebox.showerror("Character Creation", f"Échec d'export:\n{exc}")
            return

        messagebox.showinfo("Character Creation", f"Fiche générée via backend '{used_backend}':\n{out}")
