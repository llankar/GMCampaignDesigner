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

from modules.pcs.character_creation.ui.prowess_editor import ProwessEditor


def _row(root, label: str, points: str = "1") -> dict:
    return {
        "label_var": tk.StringVar(master=root, value=label),
        "points_var": tk.StringVar(master=root, value=points),
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

    assert editor.get_total_spent_prowess_points() == 5


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

    assert card["limitation_label_var"].get().endswith("3")

