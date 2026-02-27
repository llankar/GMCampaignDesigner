"""UI for Savage Fate character creation flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .constants import SKILLS
from .exporters import export_character_sheet
from .points import summarize_point_budgets
from .progression import ADVANCEMENT_OPTIONS
from .rules_engine import CharacterCreationError, build_character
from .storage import CharacterDraftRepository


class CharacterCreationView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.drafts = CharacterDraftRepository()
        self.advancement_rows = []
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
        ctk.CTkLabel(scroll, text="Compétences (15 points de base, 6 favorites)", font=("Arial", 14, "bold")).grid(
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
        self.feat_widgets = []
        for idx in range(2):
            box = ctk.CTkFrame(scroll)
            box.grid(row=9 + idx, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
            name = tk.StringVar(value=f"Prouesse {idx+1}")
            opt1 = tk.StringVar(value="")
            opt2 = tk.StringVar(value="")
            opt3 = tk.StringVar(value="")
            lim = tk.StringVar(value="")
            for lbl, var, row in (
                ("Nom", name, 0),
                ("Option 1", opt1, 1),
                ("Option 2", opt2, 2),
                ("Option 3", opt3, 3),
                ("Limitation", lim, 4),
            ):
                ctk.CTkLabel(box, text=lbl).grid(row=row, column=0, sticky="w", padx=6, pady=2)
                ctk.CTkEntry(box, textvariable=var).grid(row=row, column=1, sticky="ew", padx=6, pady=2)
            box.grid_columnconfigure(1, weight=1)
            self.feat_widgets.append((name, opt1, opt2, opt3, lim))

        ctk.CTkLabel(scroll, text="Équipement", font=("Arial", 14, "bold")).grid(
            row=11, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self._entry(scroll, "Arme", "weapon", 12, 0)
        self._entry(scroll, "Armure", "armor", 12, 1)
        self._entry(scroll, "Utilitaire", "utility", 13, 0)
        self._entry(scroll, "PE Arme", "weapon_pe", 13, 1, default="1")
        self._entry(scroll, "PE Armure", "armor_pe", 14, 0, default="1")
        self._entry(scroll, "PE Utilitaire", "utility_pe", 14, 1, default="1")

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
        for name, o1, o2, o3, lim in self.feat_widgets:
            feats.append(
                {
                    "name": name.get().strip(),
                    "options": [o1.get().strip(), o2.get().strip(), o3.get().strip()],
                    "limitation": lim.get().strip(),
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
        self._render_advancement_rows()

    def _render_advancement_rows(self):
        for widget in self.advancement_frame.winfo_children():
            widget.destroy()
        self.advancement_rows = []

        advancement_count = self._safe_int(self.inputs["advancements"].get())
        if advancement_count <= 0:
            return

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

            option_var = tk.StringVar(value=ADVANCEMENT_OPTIONS[0][0])
            option_map = {label: value for value, label in ADVANCEMENT_OPTIONS}
            choice = ctk.CTkComboBox(row_frame, values=list(option_map.keys()), state="readonly")
            choice.set(ADVANCEMENT_OPTIONS[0][1])
            choice.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

            def _on_select(selected_label, var=option_var, mapping=option_map):
                var.set(mapping.get(selected_label, ""))

            choice.configure(command=_on_select)

            details_var = tk.StringVar(value="")
            ctk.CTkEntry(row_frame, textvariable=details_var, placeholder_text="Détails narratifs / mécaniques")\
                .grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))

            self.advancement_rows.append(
                {
                    "type_var": option_var,
                    "details_var": details_var,
                    "combo": choice,
                    "label_map": {value: label for value, label in ADVANCEMENT_OPTIONS},
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
        for key, var in self.inputs.items():
            var.set(str(payload.get(key, "")))

        favorites = set(payload.get("favorites") or [])
        for skill, var in self.favorite_vars.items():
            var.set(skill in favorites)

        for skill, var in self.skill_vars.items():
            var.set(str((payload.get("skills") or {}).get(skill, 0)))

        for skill, var in self.bonus_skill_vars.items():
            var.set(str((payload.get("bonus_skills") or {}).get(skill, 0)))

        feats = payload.get("feats") or []
        for idx, (name, o1, o2, o3, lim) in enumerate(self.feat_widgets):
            feat = feats[idx] if idx < len(feats) else {}
            options = feat.get("options") or []
            name.set(feat.get("name", ""))
            o1.set(options[0] if len(options) > 0 else "")
            o2.set(options[1] if len(options) > 1 else "")
            o3.set(options[2] if len(options) > 2 else "")
            lim.set(feat.get("limitation", ""))

        advancement_choices = payload.get("advancement_choices") or []
        self._render_advancement_rows()
        for idx, row in enumerate(self.advancement_rows):
            if idx >= len(advancement_choices):
                break
            entry = advancement_choices[idx] or {}
            choice_value = (entry.get("type") or "").strip() or ADVANCEMENT_OPTIONS[0][0]
            row["type_var"].set(choice_value)
            row["combo"].set(row["label_map"].get(choice_value, ADVANCEMENT_OPTIONS[0][1]))
            row["details_var"].set((entry.get("details") or "").strip())

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
        summary = summarize_point_budgets(base_points, bonus_points, favorites)
        self.remaining_points_var.set(
            f"Base restants: {summary['remaining_base']} | "
            f"Bonus restants: {summary['remaining_bonus']}"
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
