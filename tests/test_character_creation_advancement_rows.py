import sys
import tkinter as tk
import types


class _DummyWidget:
    def __init__(self, master=None, *args, **kwargs):
        self.master = master
        self._children = []
        if hasattr(master, "_children"):
            master._children.append(self)

    def grid(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def destroy(self):
        return None

    def winfo_children(self):
        return list(self._children)


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkComboBox=_DummyWidget,
        CTkEntry=_DummyWidget,
        CTkCheckBox=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkScrollableFrame=_DummyWidget,
    ),
)

from modules.pcs.character_creation.view import CharacterCreationView
import modules.pcs.character_creation.view as view_module


def test_advancement_choices_are_preserved_when_available_count_changes(monkeypatch):
    root = tk.Tcl()

    original_string_var = view_module.tk.StringVar

    def _string_var_with_tcl_master(*args, **kwargs):
        kwargs.setdefault("master", root)
        return original_string_var(*args, **kwargs)

    monkeypatch.setattr(view_module.tk, "StringVar", _string_var_with_tcl_master)
    view = CharacterCreationView.__new__(CharacterCreationView)
    view.advancement_frame = _DummyWidget()
    view.advancement_rows = [
        {
            "type_var": tk.StringVar(master=root, value="skill_improvement"),
            "details_var": tk.StringVar(master=root, value="Combat"),
        }
    ]
    view._advancement_choices_cache = []
    view.inputs = {"advancements": tk.StringVar(master=root, value="3")}

    view._render_advancement_rows()

    assert len(view.advancement_rows) == 3
    assert view.advancement_rows[0]["type_var"].get() == "skill_improvement"
    assert view.advancement_rows[0]["details_var"].get() == "Combat"

    view.advancement_rows[1]["type_var"].set("prowess_points")
    view.advancement_rows[1]["details_var"].set("Perception")

    view.inputs["advancements"].set("4")
    view._render_advancement_rows()

    assert len(view.advancement_rows) == 4
    assert view.advancement_rows[0]["details_var"].get() == "Combat"
    assert view.advancement_rows[1]["type_var"].get() == "prowess_points"
    assert view.advancement_rows[1]["details_var"].get() == "Perception"
