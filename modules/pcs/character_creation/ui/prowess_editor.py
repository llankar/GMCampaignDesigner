"""Composable prowess editor for character creation."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from .prowess.options import (
    DEFAULT_OPTION_NAME,
    PROWESS_OPTION_BY_LABEL,
    PROWESS_OPTION_LABELS,
    option_uses_variable_points,
    parse_variable_points,
)

POINT_EFFECT_BY_LEVEL = {1: "+3", 2: "+5", 3: "+7"}


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
            text="Nom",
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
            variable_points_var = tk.StringVar(value=str(parse_variable_points(option_detail)))

            ctk.CTkLabel(box, text=f"Option {option_idx + 1}").grid(row=option_idx + 1, column=0, sticky="w", padx=6, pady=2)

            row_box = ctk.CTkFrame(box)
            row_box.grid(row=option_idx + 1, column=1, sticky="ew", padx=6, pady=2)
            row_box.grid_columnconfigure(0, weight=1)

            combo = ctk.CTkComboBox(row_box, values=PROWESS_OPTION_LABELS, variable=option_label_var, state="readonly")
            combo.grid(row=0, column=0, sticky="ew")

            points_combo = ctk.CTkComboBox(row_box, values=["1", "2", "3"], variable=variable_points_var, state="readonly", width=70)
            points_combo.grid(row=0, column=1, sticky="e", padx=(6, 0))
            points_label = ctk.CTkLabel(row_box, text="pt")
            points_label.grid(row=0, column=2, sticky="w", padx=(4, 0))

            detail_entry = ctk.CTkEntry(
                row_box,
                textvariable=option_detail_var,
                placeholder_text="Détails (facultatif)",
            )
            detail_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 0))

            row_data = {
                "label_var": option_label_var,
                "detail_var": option_detail_var,
                "combo": combo,
                "points_var": variable_points_var,
                "points_combo": points_combo,
                "points_label": points_label,
            }
            option_rows.append(row_data)

            def _on_option_changed(*_args, row=row_data):
                self._sync_variable_points_visibility(row)

            option_label_var.trace_add("write", _on_option_changed)
            self._sync_variable_points_visibility(row_data)

        limitation_var = tk.StringVar(value=(feat.get("limitation") or "").strip())
        ctk.CTkLabel(box, text=f"Limitation | Points de prouesse utilisés: {prowess_points}").grid(row=4, column=0, sticky="w", padx=6, pady=2)
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
                option_name = PROWESS_OPTION_BY_LABEL.get(option_label, DEFAULT_OPTION_NAME)
                detail = option_row["detail_var"].get().strip()

                if option_uses_variable_points(option_name):
                    points = parse_variable_points(option_row["points_var"].get())
                    effect = POINT_EFFECT_BY_LEVEL[points]
                    composed_detail = f"{points} pt ({effect})"
                    if detail:
                        composed_detail = f"{composed_detail} - {detail}"
                    options.append(f"{option_name} : {composed_detail}")
                else:
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

    def _sync_variable_points_visibility(self, row_data: dict) -> None:
        option_label = row_data["label_var"].get()
        option_name = PROWESS_OPTION_BY_LABEL.get(option_label, DEFAULT_OPTION_NAME)
        uses_variable_points = option_uses_variable_points(option_name)
        if uses_variable_points:
            row_data["points_combo"].grid()
            row_data["points_label"].grid()
        else:
            row_data["points_combo"].grid_remove()
            row_data["points_label"].grid_remove()
