import sys
import tkinter as tk
import types


class _StubWidget:
    def __init__(self, *args, **kwargs):
        self._grid_visible = True

    def grid(self, *args, **kwargs):
        self._grid_visible = True
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def grid_remove(self):
        self._grid_visible = False
        return None

    def destroy(self):
        return None

    def configure(self, **kwargs):
        return None


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=_StubWidget,
        CTkLabel=_StubWidget,
        CTkComboBox=_StubWidget,
        CTkEntry=_StubWidget,
        CTkButton=_StubWidget,
    ),
)

from modules.pcs.character_creation.ui.prowess.options import PROWESS_OPTION_LABELS
from modules.pcs.character_creation.ui.prowess_editor import ProwessEditor


def _label_for(prefix: str) -> str:
    return next(label for label in PROWESS_OPTION_LABELS if label.startswith(prefix))


def _row(root, label: str, points: str = "1", detail: str = "", mode: str = "Contact") -> dict:
    return {
        "label_var": tk.StringVar(master=root, value=_label_for(label)),
        "points_var": tk.StringVar(master=root, value=points),
        "damage_mode_var": tk.StringVar(master=root, value=mode),
        "detail_var": tk.StringVar(master=root, value=detail),
        "points_combo": _StubWidget(),
        "points_label": _StubWidget(),
        "damage_mode_combo": _StubWidget(),
        "detail_entry": _StubWidget(),
        "row_box": _StubWidget(),
        "remove_button": _StubWidget(),
    }


def test_get_total_spent_prowess_points_uses_variable_option_costs():
    root = tk.Tcl()
    editor = ProwessEditor.__new__(ProwessEditor)
    editor._cards = [
        {
            "options": [
                _row(root, "Bonus dommages", "3"),
                _row(root, "Armure", "2"),
                _row(root, "Perce Armure", "1"),
            ]
        }
    ]

    assert editor.get_total_spent_prowess_points() == 6


def test_refresh_feat_card_ui_updates_label_with_variable_option_costs():
    root = tk.Tcl()
    editor = ProwessEditor.__new__(ProwessEditor)
    card = {
        "options": [
            _row(root, "Bonus dommages", "3"),
            _row(root, "Perce Armure", "1"),
        ],
        "limitation_label_var": tk.StringVar(master=root, value=""),
    }

    editor._refresh_feat_card_ui(card)

    assert card["limitation_label_var"].get().endswith("4")


def test_sync_variable_points_visibility_handles_bonus_damage_mode_widgets():
    root = tk.Tcl()
    editor = ProwessEditor.__new__(ProwessEditor)

    bonus_row = _row(root, "Bonus dommages", "2", mode="Distance")
    editor._sync_variable_points_visibility(bonus_row)
    assert bonus_row["damage_mode_combo"]._grid_visible is True
    assert bonus_row["detail_entry"]._grid_visible is False

    armor_row = _row(root, "Armure", "2")
    editor._sync_variable_points_visibility(armor_row)
    assert armor_row["damage_mode_combo"]._grid_visible is False
    assert armor_row["detail_entry"]._grid_visible is True


def test_get_payload_serializes_bonus_damage_with_mode_and_scale():
    root = tk.Tcl()
    editor = ProwessEditor.__new__(ProwessEditor)
    editor._cards = [
        {
            "name_var": tk.StringVar(master=root, value="Frappe précise"),
            "options": [_row(root, "Bonus dommages", points="2", mode="Distance")],
            "limitation_var": tk.StringVar(master=root, value=""),
        }
    ]

    payload = editor.get_payload()

    assert payload[0]["options"] == ["Bonus dommages : Distance, 2 pt (+4)"]
    assert payload[0]["prowess_points"] == 2


def test_get_payload_serializes_armor_with_three_armor_per_point():
    root = tk.Tcl()
    editor = ProwessEditor.__new__(ProwessEditor)
    editor._cards = [
        {
            "name_var": tk.StringVar(master=root, value="Carapace"),
            "options": [_row(root, "Armure", points="2")],
            "limitation_var": tk.StringVar(master=root, value=""),
        }
    ]

    payload = editor.get_payload()

    assert payload[0]["options"] == ["Armure : 2 pt (+6)"]
    assert payload[0]["prowess_points"] == 2


def test_request_feat_removal_calls_callback_with_feat_index():
    root = tk.Tcl()
    captured: list[int] = []
    editor = ProwessEditor.__new__(ProwessEditor)
    editor._on_remove_feat = captured.append
    card0 = {"name_var": tk.StringVar(master=root, value="Prouesse 1")}
    card1 = {"name_var": tk.StringVar(master=root, value="Prouesse 2")}
    editor._cards = [card0, card1]

    editor._request_feat_removal(card1)

    assert captured == [1]
