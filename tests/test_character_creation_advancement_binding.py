import sys
import tkinter as tk
import types


class _StubWidget:
    def __init__(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def destroy(self):
        return None


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=_StubWidget,
        CTkLabel=_StubWidget,
        CTkComboBox=_StubWidget,
        CTkEntry=_StubWidget,
        CTkCheckBox=_StubWidget,
        CTkButton=_StubWidget,
        CTkScrollableFrame=_StubWidget,
    ),
)

from modules.pcs.character_creation.progression import ADVANCEMENT_OPTIONS
from modules.pcs.character_creation.ui.advancement_binding import bind_advancement_type_and_label_vars
from modules.pcs.character_creation.view import CharacterCreationView
import modules.pcs.character_creation.view as view_module


def test_binding_updates_internal_type_and_calls_callback_on_label_change():
    root = tk.Tcl()
    value_to_label = {value: label for value, label in ADVANCEMENT_OPTIONS}
    label_to_value = {label: value for value, label in ADVANCEMENT_OPTIONS}
    type_var = tk.StringVar(master=root, value=ADVANCEMENT_OPTIONS[0][0])
    label_var = tk.StringVar(master=root, value=value_to_label[ADVANCEMENT_OPTIONS[0][0]])
    callback_calls = []

    bind_advancement_type_and_label_vars(
        type_var=type_var,
        label_var=label_var,
        label_to_value=label_to_value,
        value_to_label=value_to_label,
        on_type_updated=lambda *_args: callback_calls.append(type_var.get()),
    )

    label_var.set(value_to_label["prowess_points"])

    assert type_var.get() == "prowess_points"
    assert callback_calls[-1] == "prowess_points"


def test_render_feat_rows_uses_updated_advancement_type_for_prowess_budget(monkeypatch):
    root = tk.Tcl()
    captured = {}

    def fake_prowess_points_from_advancement_choices(choices):
        captured["choices"] = choices
        return []

    monkeypatch.setattr(view_module, "prowess_points_from_advancement_choices", fake_prowess_points_from_advancement_choices)
    monkeypatch.setattr(view_module, "BASE_FEAT_COUNT", 0)

    view = CharacterCreationView.__new__(CharacterCreationView)
    view.feat_frame = types.SimpleNamespace(winfo_children=lambda: [])
    view.feat_widgets = []
    view.feat_count_var = tk.StringVar(master=root, value="")
    view.advancement_rows = [
        {
            "type_var": tk.StringVar(master=root, value="prowess_points"),
            "details_var": tk.StringVar(master=root, value="test"),
        }
    ]

    view._render_feat_rows(existing_feats=[])

    assert captured["choices"][0]["type"] == "prowess_points"
