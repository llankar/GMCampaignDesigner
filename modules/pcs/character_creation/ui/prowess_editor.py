"""Composable prowess editor for character creation."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ..prowess import calculate_feat_points_from_options
from .prowess.options import (
    DEFAULT_OPTION_NAME,
    BONUS_DAMAGE_MODES,
    PROWESS_OPTION_BY_LABEL,
    PROWESS_OPTION_LABELS,
    option_uses_variable_points,
    parse_bonus_damage_detail,
    parse_variable_points,
)

DAMAGE_EFFECT_BY_MODE = {
    "Distance": {1: "+2", 2: "+4", 3: "+6"},
    "Contact": {1: "+3", 2: "+5", 3: "+7"},
}
POINT_EFFECT_BY_LEVEL = DAMAGE_EFFECT_BY_MODE["Contact"]
ARMOR_EFFECT_BY_LEVEL = {1: "+3", 2: "+6", 3: "+9"}


class ProwessEditor:
    def __init__(self, parent, on_change=None, on_remove_feat=None, grid_row: int = 9):
        """Initialize the ProwessEditor instance."""
        self.frame = ctk.CTkFrame(parent)
        self.frame.grid(row=grid_row, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        for column in range(3):
            self.frame.grid_columnconfigure(column, weight=1)
        self._cards: list[dict] = []
        self._on_change = on_change
        self._on_remove_feat = on_remove_feat

    def set_feat_rows(self, total_feats: int, existing_feats: list[dict] | None = None, _legacy_existing_feats: list[dict] | None = None) -> None:
        """Set feat rows."""
        if _legacy_existing_feats is not None:
            existing_feats = _legacy_existing_feats

        current_payload = self.get_payload()
        source_feats = existing_feats if existing_feats else current_payload

        for widget in self.frame.winfo_children():
            widget.destroy()
        self._cards = []

        for idx in range(total_feats):
            feat = source_feats[idx] if idx < len(source_feats) else {}
            self._cards.append(self._build_feat_card(idx, feat))

    def _build_feat_card(self, idx: int, feat: dict) -> dict:
        """Build feat card."""
        box = ctk.CTkFrame(self.frame)
        row = idx // 3
        column = idx % 3
        box.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
        box.grid_columnconfigure(1, weight=1)

        name_var = tk.StringVar(value=(feat.get("name") or f"Prouesse {idx + 1}").strip())
        ctk.CTkLabel(box, text="Nom").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ctk.CTkEntry(box, textvariable=name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=2)

        options_container = ctk.CTkFrame(box)
        options_container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=2)
        options_container.grid_columnconfigure(0, weight=1)

        option_rows: list[dict] = []
        options = feat.get("options") or []
        if not options:
            options = [""]

        limitation_var = tk.StringVar(value=(feat.get("limitation") or "").strip())
        limitation_label_var = tk.StringVar(value="")

        add_option_button = ctk.CTkButton(
            box,
            text="+ Ajouter un bonus",
            width=160,
            command=lambda: None,
        )
        add_option_button.grid(row=2, column=0, sticky="w", padx=6, pady=(2, 2))

        remove_feat_button = ctk.CTkButton(
            box,
            text="Effacer prouesse",
            width=160,
            command=lambda: None,
        )
        remove_feat_button.grid(row=2, column=1, sticky="e", padx=6, pady=(2, 2))

        card = {
            "name_var": name_var,
            "options": option_rows,
            "limitation_var": limitation_var,
            "limitation_label_var": limitation_label_var,
            "options_container": options_container,
            "box": box,
            "remove_feat_button": remove_feat_button,
        }

        add_option_button.configure(command=lambda c=card: self._append_option_row(c, ""))
        remove_feat_button.configure(command=lambda c=card: self._request_feat_removal(c))

        for raw_value in options:
            self._append_option_row(card, raw_value)

        ctk.CTkLabel(box, textvariable=limitation_label_var).grid(row=3, column=0, sticky="w", padx=6, pady=2)
        ctk.CTkEntry(box, textvariable=limitation_var, placeholder_text="Texte libre").grid(
            row=3,
            column=1,
            sticky="ew",
            padx=6,
            pady=2,
        )

        self._refresh_feat_card_ui(card)
        name_var.trace_add("write", lambda *_: self._notify_change())
        limitation_var.trace_add("write", lambda *_: self._notify_change())
        return card

    def _append_option_row(self, card: dict, raw_value: str) -> None:
        """Append option row."""
        option_name, option_detail = self._split_option_value(raw_value)
        option_label = self._label_for_option(option_name)

        option_label_var = tk.StringVar(value=option_label)
        option_detail_var = tk.StringVar(value=option_detail)
        damage_mode, parsed_points = parse_bonus_damage_detail(option_detail)
        variable_points_var = tk.StringVar(value=str(parsed_points))
        damage_mode_var = tk.StringVar(value=damage_mode)

        row_box = ctk.CTkFrame(card["options_container"])
        row_box.grid_columnconfigure(0, weight=1)

        combo = ctk.CTkComboBox(row_box, values=PROWESS_OPTION_LABELS, variable=option_label_var, state="readonly")
        combo.grid(row=0, column=0, sticky="ew")

        points_combo = ctk.CTkComboBox(row_box, values=["1", "2", "3"], variable=variable_points_var, state="readonly", width=70)
        points_combo.grid(row=0, column=1, sticky="e", padx=(6, 0))
        points_label = ctk.CTkLabel(row_box, text="pt")
        points_label.grid(row=0, column=2, sticky="w", padx=(4, 0))

        damage_mode_combo = ctk.CTkComboBox(
            row_box,
            values=list(BONUS_DAMAGE_MODES),
            variable=damage_mode_var,
            state="readonly",
            width=100,
        )
        damage_mode_combo.grid(row=0, column=3, sticky="e", padx=(6, 0))

        remove_button = ctk.CTkButton(row_box, text="Supprimer", width=95)
        remove_button.grid(row=0, column=4, padx=(6, 0))

        detail_entry = ctk.CTkEntry(
            row_box,
            textvariable=option_detail_var,
            placeholder_text="Détails (facultatif)",
        )
        detail_entry.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(2, 0))

        row_data: dict = {
            "label_var": option_label_var,
            "detail_var": option_detail_var,
            "combo": combo,
            "points_var": variable_points_var,
            "points_combo": points_combo,
            "points_label": points_label,
            "damage_mode_var": damage_mode_var,
            "damage_mode_combo": damage_mode_combo,
            "detail_entry": detail_entry,
            "row_box": row_box,
            "remove_button": remove_button,
        }
        remove_button.configure(command=lambda c=card, r=row_data: self._remove_option_row(c, r))
        card["options"].append(row_data)

        option_label_var.trace_add("write", lambda *_: self._on_option_updated(card, row_data))
        option_detail_var.trace_add("write", lambda *_: self._notify_change())
        variable_points_var.trace_add("write", lambda *_: self._notify_change())
        damage_mode_var.trace_add("write", lambda *_: self._notify_change())
        self._on_option_updated(card, row_data)
        self._refresh_feat_card_ui(card)
        self._notify_change()

    def _remove_option_row(self, card: dict, row_data: dict) -> None:
        """Remove option row."""
        if len(card["options"]) <= 1:
            return
        row_data["row_box"].destroy()
        card["options"] = [row for row in card["options"] if row is not row_data]
        self._refresh_feat_card_ui(card)
        self._notify_change()

    def _refresh_feat_card_ui(self, card: dict) -> None:
        """Refresh feat card UI."""
        remove_button = card.get("remove_feat_button")
        cards = getattr(self, "_cards", [card])
        if remove_button is not None:
            if len(cards) <= 1:
                remove_button.grid_remove()
            else:
                remove_button.grid()

        for idx, option_row in enumerate(card["options"]):
            # Process each (idx, option_row) from enumerate(card['options']).
            option_row["row_box"].grid(row=idx, column=0, sticky="ew", pady=2)
            if len(card["options"]) <= 1:
                option_row["remove_button"].grid_remove()
            else:
                option_row["remove_button"].grid()

        prowess_points = self._prowess_points_for_card(card)
        card["limitation_label_var"].set(f"Limitation | Points de prouesse utilisés: {prowess_points}")

    def _request_feat_removal(self, card: dict) -> None:
        """Internal helper for request feat removal."""
        if callable(self._on_remove_feat):
            self._on_remove_feat(self._cards.index(card))

    @staticmethod
    def _option_mode_is_bonus_damage(option_name: str) -> bool:
        """Internal helper for option mode is bonus damage."""
        return option_name == "Bonus dommages"

    def _effect_for_option(self, option_name: str, points: int, damage_mode: str | None = None) -> str:
        """Internal helper for effect for option."""
        if self._option_mode_is_bonus_damage(option_name):
            mode = damage_mode if damage_mode in BONUS_DAMAGE_MODES else BONUS_DAMAGE_MODES[0]
            return DAMAGE_EFFECT_BY_MODE[mode][points]
        if option_name == "Armure":
            return ARMOR_EFFECT_BY_LEVEL[points]
        return POINT_EFFECT_BY_LEVEL[points]

    def _serialize_option_row(self, option_row: dict) -> str:
        """Serialize option row."""
        option_label = option_row["label_var"].get()
        option_name = PROWESS_OPTION_BY_LABEL.get(option_label, DEFAULT_OPTION_NAME)
        detail = option_row["detail_var"].get().strip()

        if option_uses_variable_points(option_name):
            # Handle the branch where option_uses_variable_points(option_name).
            points = parse_variable_points(option_row["points_var"].get())
            if self._option_mode_is_bonus_damage(option_name):
                # Handle the branch where _option_mode_is_bonus_damage(option_name).
                mode = option_row["damage_mode_var"].get().strip()
                if mode not in BONUS_DAMAGE_MODES:
                    mode = BONUS_DAMAGE_MODES[0]
                effect = self._effect_for_option(option_name, points, mode)
                composed_detail = f"{mode}, {points} pt ({effect})"
            else:
                effect = self._effect_for_option(option_name, points)
                composed_detail = f"{points} pt ({effect})"
            if detail:
                composed_detail = f"{composed_detail} - {detail}"
            return f"{option_name} : {composed_detail}"

        return f"{option_name} : {detail}" if detail else option_name

    def get_payload(self) -> list[dict]:
        """Return payload."""
        feats = []
        for card in self._cards:
            # Process each card from _cards.
            options = []
            for option_row in card["options"]:
                options.append(self._serialize_option_row(option_row))

            feats.append(
                {
                    "name": card["name_var"].get().strip(),
                    "options": options,
                    "limitation": card["limitation_var"].get().strip(),
                    "prowess_points": self._prowess_points_for_card(card),
                }
            )
        return feats

    def get_total_spent_prowess_points(self) -> int:
        """Return total spent prowess points."""
        return sum(self._prowess_points_for_card(card) for card in self._cards)

    def _prowess_points_for_card(self, card: dict) -> int:
        """Internal helper for prowess points for card."""
        serialized_options = [self._serialize_option_row(option_row) for option_row in card["options"]]
        return calculate_feat_points_from_options(serialized_options)

    def _prowess_cost_for_option_row(self, option_row: dict) -> int:
        """Internal helper for prowess cost for option row."""
        option_label = option_row["label_var"].get()
        option_name = PROWESS_OPTION_BY_LABEL.get(option_label, DEFAULT_OPTION_NAME)
        if option_uses_variable_points(option_name):
            return parse_variable_points(option_row["points_var"].get())
        return 1

    def _label_for_option(self, option_name: str) -> str:
        """Internal helper for label for option."""
        for label, name in PROWESS_OPTION_BY_LABEL.items():
            if option_name == name:
                return label
        return PROWESS_OPTION_LABELS[0]

    @staticmethod
    def _split_option_value(raw_value: str) -> tuple[str, str]:
        """Internal helper for split option value."""
        if ":" not in raw_value:
            return raw_value.strip(), ""
        option_name, option_detail = raw_value.split(":", 1)
        return option_name.strip(), option_detail.strip()

    def _sync_variable_points_visibility(self, row_data: dict) -> None:
        """Synchronize variable points visibility."""
        option_label = row_data["label_var"].get()
        option_name = PROWESS_OPTION_BY_LABEL.get(option_label, DEFAULT_OPTION_NAME)
        uses_variable_points = option_uses_variable_points(option_name)
        is_bonus_damage = self._option_mode_is_bonus_damage(option_name)

        if uses_variable_points:
            row_data["points_combo"].grid()
            row_data["points_label"].grid()
        else:
            row_data["points_combo"].grid_remove()
            row_data["points_label"].grid_remove()

        if is_bonus_damage:
            row_data["damage_mode_combo"].grid()
            row_data["detail_entry"].grid_remove()
        else:
            row_data["damage_mode_combo"].grid_remove()
            row_data["detail_entry"].grid()

    def _on_option_updated(self, card: dict, row_data: dict) -> None:
        """Handle option updated."""
        self._sync_variable_points_visibility(row_data)
        self._refresh_feat_card_ui(card)
        self._notify_change()

    def _notify_change(self) -> None:
        """Notify change."""
        if callable(self._on_change):
            self._on_change()
