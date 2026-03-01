"""Composable prowess editor for character creation."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

PROWESS_OPTION_DEFINITIONS = [
    ("Bonus dommages", "+3 à +7 CàC (+4 en risque) ou +2 à +6 à distance (+4 en risque)."),
    ("Armure", "+3 Armure (max 2 fois, ou 4 fois pour Super Héros)."),
    ("Perce Armure", "Ignore 3 d'armure (max 2 fois, ou 4 fois pour Super Héros)."),
    ("Utilisation non conventionnelle", "Permet d'utiliser une compétence à la place d'une autre."),
    ("Effet particulier", "Ajoute un effet particulier (invisibilité, feu, paralysie, etc.)."),
    ("Durée étendue", "Un effet qui dure une scène."),
    ("Portée étendue", "La prouesse fonctionne au-delà de la ligne de vue."),
    ("Zone d'effet", "Affecte un groupe (bonus variable vs groupe)."),
    ("Bonus aux jets", "+1 sur un jet (max 2 fois)."),
    ("Limitation de l'effet", "Ajoute une contrainte (1/scène, atout, condition, etc.)."),
    ("Compétence*", "D12 en compétence ou +2 après D12 (Super Héros uniquement)."),
    ("Vitesse*", "Mouvement X2 puis jusqu'à des paliers extrêmes (Super Héros uniquement)."),
]

PROWESS_OPTION_LABELS = [f"{name} — {description}" for name, description in PROWESS_OPTION_DEFINITIONS]
PROWESS_OPTION_BY_LABEL = {
    label: name for label, (name, _description) in zip(PROWESS_OPTION_LABELS, PROWESS_OPTION_DEFINITIONS)
}


class ProwessEditor:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent)
        self.frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        self._cards: list[dict] = []

    def set_feat_rows(self, total_feats: int, prowess_budgets: list[int], existing_feats: list[dict]) -> None:
        current_payload = self.get_payload()
        source_feats = existing_feats if existing_feats else current_payload

        for widget in self.frame.winfo_children():
            widget.destroy()
        self._cards = []

        for idx in range(total_feats):
            feat = source_feats[idx] if idx < len(source_feats) else {}
            prowess_points = 0 if idx < (total_feats - len(prowess_budgets)) else prowess_budgets[idx - (total_feats - len(prowess_budgets))]
            self._cards.append(self._build_feat_card(idx, feat, prowess_points))

    def _build_feat_card(self, idx: int, feat: dict, prowess_points: int) -> dict:
        box = ctk.CTkFrame(self.frame)
        box.grid(row=idx, column=0, sticky="ew", pady=3)
        box.grid_columnconfigure(1, weight=1)

        name_var = tk.StringVar(value=(feat.get("name") or f"Prouesse {idx + 1}").strip())
        ctk.CTkLabel(
            box,
            text=("Nom" if prowess_points <= 0 else f"Nom ({prowess_points} pt{'s' if prowess_points > 1 else ''} de prouesse)"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ctk.CTkEntry(box, textvariable=name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=2)

        options = feat.get("options") or []
        option_rows: list[dict] = []
        for option_idx in range(3):
            raw_value = options[option_idx] if option_idx < len(options) else ""
            option_name, option_detail = self._split_option_value(raw_value)
            option_label = self._label_for_option(option_name)

            option_label_var = tk.StringVar(value=option_label)
            option_detail_var = tk.StringVar(value=option_detail)
            ctk.CTkLabel(box, text=f"Option {option_idx + 1}").grid(row=option_idx + 1, column=0, sticky="w", padx=6, pady=2)

            row_box = ctk.CTkFrame(box)
            row_box.grid(row=option_idx + 1, column=1, sticky="ew", padx=6, pady=2)
            row_box.grid_columnconfigure(0, weight=1)

            combo = ctk.CTkComboBox(row_box, values=PROWESS_OPTION_LABELS, variable=option_label_var, state="readonly")
            combo.grid(row=0, column=0, sticky="ew")
            ctk.CTkEntry(
                row_box,
                textvariable=option_detail_var,
                placeholder_text="Détails (facultatif)",
            ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

            option_rows.append(
                {
                    "label_var": option_label_var,
                    "detail_var": option_detail_var,
                    "combo": combo,
                }
            )

        limitation_var = tk.StringVar(value=(feat.get("limitation") or "").strip())
        ctk.CTkLabel(box, text="Limitation").grid(row=4, column=0, sticky="w", padx=6, pady=2)
        ctk.CTkEntry(box, textvariable=limitation_var, placeholder_text="Texte libre").grid(
            row=4, column=1, sticky="ew", padx=6, pady=2
        )

        return {
            "name_var": name_var,
            "options": option_rows,
            "limitation_var": limitation_var,
            "prowess_points": prowess_points,
        }

    def get_payload(self) -> list[dict]:
        feats = []
        for card in self._cards:
            options = []
            for option_row in card["options"]:
                option_label = option_row["label_var"].get()
                option_name = PROWESS_OPTION_BY_LABEL.get(option_label, PROWESS_OPTION_DEFINITIONS[0][0])
                detail = option_row["detail_var"].get().strip()
                options.append(f"{option_name} : {detail}" if detail else option_name)

            feats.append(
                {
                    "name": card["name_var"].get().strip(),
                    "options": options,
                    "limitation": card["limitation_var"].get().strip(),
                    "prowess_points": card["prowess_points"],
                }
            )
        return feats

    def _label_for_option(self, option_name: str) -> str:
        for label, name in PROWESS_OPTION_BY_LABEL.items():
            if option_name == name:
                return label
        return PROWESS_OPTION_LABELS[0]

    @staticmethod
    def _split_option_value(raw_value: str) -> tuple[str, str]:
        if ":" not in raw_value:
            return raw_value.strip(), ""
        option_name, option_detail = raw_value.split(":", 1)
        return option_name.strip(), option_detail.strip()
