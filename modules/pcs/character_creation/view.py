"""UI for Savage Fate character creation flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .constants import SKILLS
from .exporters import BACKENDS, export_character_sheet
from .points import summarize_point_budgets
from .rules_engine import CharacterCreationError, build_character


class CharacterCreationView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
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

        self.favorite_vars = {}
        self.skill_vars = {}
        ctk.CTkLabel(scroll, text="Compétences (15 points, 6 favorites)", font=("Arial", 14, "bold")).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(10, 2)
        )
        self.remaining_points_var = tk.StringVar(value="Points restants: 15 | Bonus favoris dispo: 0")
        ctk.CTkLabel(scroll, textvariable=self.remaining_points_var, font=("Arial", 12, "bold")).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4)
        )
        skill_frame = ctk.CTkFrame(scroll)
        skill_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        for i, skill in enumerate(SKILLS):
            r = i // 2
            c = (i % 2) * 3
            ctk.CTkLabel(skill_frame, text=skill).grid(row=r, column=c, sticky="w", padx=(6, 2), pady=2)
            fav = tk.BooleanVar(value=i < 6)
            pts = tk.StringVar(value="0")
            self.favorite_vars[skill] = fav
            self.skill_vars[skill] = pts
            ctk.CTkCheckBox(skill_frame, text="Fav", variable=fav, onvalue=True, offvalue=False).grid(row=r, column=c + 1)
            ctk.CTkEntry(skill_frame, textvariable=pts, width=55).grid(row=r, column=c + 2, padx=(2, 10))
            fav.trace_add("write", self._update_remaining_points_marker)
            pts.trace_add("write", self._update_remaining_points_marker)

        ctk.CTkLabel(scroll, text="Prouesses", font=("Arial", 14, "bold")).grid(
            row=6, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self.feat_widgets = []
        for idx in range(2):
            box = ctk.CTkFrame(scroll)
            box.grid(row=7 + idx, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
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
            row=9, column=0, sticky="w", padx=6, pady=(10, 2)
        )
        self._entry(scroll, "Arme", "weapon", 10, 0)
        self._entry(scroll, "Armure", "armor", 10, 1)
        self._entry(scroll, "Utilitaire", "utility", 11, 0)
        self._entry(scroll, "PE Arme", "weapon_pe", 11, 1, default="1")
        self._entry(scroll, "PE Armure", "armor_pe", 12, 0, default="1")
        self._entry(scroll, "PE Utilitaire", "utility_pe", 12, 1, default="1")

        self._update_remaining_points_marker()

        export_row = ctk.CTkFrame(self)
        export_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        export_row.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(export_row, text="Backend:").grid(row=0, column=0, padx=(0, 6))
        self.export_backend_var = tk.StringVar(value="fitz")
        ctk.CTkOptionMenu(export_row, variable=self.export_backend_var, values=list(BACKENDS), width=110).grid(
            row=0, column=1, padx=(0, 10)
        )

        self.export_html_only_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(export_row, text="Export HTML seul", variable=self.export_html_only_var).grid(
            row=0, column=2, sticky="w"
        )

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
        return {
            "name": self.inputs["name"].get().strip(),
            "player": self.inputs["player"].get().strip(),
            "concept": self.inputs["concept"].get().strip(),
            "flaw": self.inputs["flaw"].get().strip(),
            "group_asset": self.inputs["group_asset"].get().strip(),
            "advancements": int(self.inputs["advancements"].get() or 0),
            "favorites": favorites,
            "skills": {skill: int((var.get() or "0")) for skill, var in self.skill_vars.items()},
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

    def _safe_int(self, raw_value: str) -> int:
        try:
            return int((raw_value or "0").strip())
        except ValueError:
            return 0

    def _update_remaining_points_marker(self, *_args) -> None:
        base_points = {skill: self._safe_int(var.get()) for skill, var in self.skill_vars.items()}
        favorites = [skill for skill, var in self.favorite_vars.items() if var.get()]
        summary = summarize_point_budgets(base_points, favorites)
        self.remaining_points_var.set(
            f"Points restants: {summary['remaining_base']} | "
            f"Bonus favoris dispo: {summary['free_favored_points']}"
        )

    def create_character_pdf(self):
        try:
            payload = self._build_payload()
            result = build_character(payload)
        except (ValueError, CharacterCreationError) as exc:
            messagebox.showerror("Character Creation", str(exc))
            return

        backend = self.export_backend_var.get()
        html_only = self.export_html_only_var.get()

        extension = ".html" if html_only else (".docx" if backend == "docx" else ".pdf")
        kind = "HTML" if html_only else ("DOCX" if backend == "docx" else "PDF")
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
