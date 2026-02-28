import sys
import tkinter as tk
import types


class _StubWidget:
    def __init__(self, master=None, *args, **kwargs):
        self.master = master
        self._grid_visible = True

    def grid(self, *args, **kwargs):
        self._grid_visible = True
        self._grid_kwargs = kwargs
        return None

    def grid_remove(self):
        self._grid_visible = False
        return None

    def grid_configure(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def destroy(self):
        return None


class _StubLabel(_StubWidget):
    pass


class _StubFrame(_StubWidget):
    pass


class _StubEntry(_StubWidget):
    pass


class _StubButton(_StubWidget):
    def __init__(self, master=None, *args, command=None, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.command = command


class _StubComboBox(_StubWidget):
    def __init__(self, master=None, *args, values=None, command=None, **kwargs):
        super().__init__(master, *args, **kwargs)
        self._values = list(values or [])
        self._value = ""
        self._command = command

    def set(self, value):
        self._value = value

    def get(self):
        return self._value

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._values = list(kwargs["values"])
        if "command" in kwargs:
            self._command = kwargs["command"]

    def cget(self, key):
        if key == "values":
            return self._values
        raise KeyError(key)


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=_StubFrame,
        CTkLabel=_StubLabel,
        CTkEntry=_StubEntry,
        CTkComboBox=_StubComboBox,
        CTkButton=_StubButton,
    ),
)

import modules.pcs.character_creation.ui.equipment_editor as editor_module

EquipmentEditor = editor_module.EquipmentEditor


def _build_editor(max_level=3):
    root = tk.Tcl()
    original_string_var = editor_module.tk.StringVar

    def _string_var_with_tcl_master(*args, **kwargs):
        kwargs.setdefault("master", root)
        return original_string_var(*args, **kwargs)

    editor_module.tk.StringVar = _string_var_with_tcl_master
    editor = EquipmentEditor(
        parent=_StubFrame(),
        on_change=lambda: None,
        max_level_provider=lambda: max_level,
    )
    return root, editor


def test_can_remove_effect_row_from_existing_object():
    _, editor = _build_editor()

    editor.add_effect_row("weapon")
    assert len(editor._columns["weapon"]["rows"]) == 2

    first_row = editor._columns["weapon"]["rows"][0]["frame"]
    editor.remove_effect_row("weapon", first_row)

    assert len(editor._columns["weapon"]["rows"]) == 1


def test_remove_and_readd_object_slot_updates_visibility_and_payload():
    _, editor = _build_editor()

    editor.add_object_slot()

    editor._columns["armor"]["name_var"].set("Cuirasse")
    editor.remove_object_slot("armor")

    assert "armor" not in editor._active_object_keys
    assert editor.get_equipment_names()["armor"] == ""
    assert editor.get_allocated_pe()["armor"] == 0

    editor.add_object_slot()

    assert "armor" in editor._active_object_keys
    assert len(editor._columns["armor"]["rows"]) == 1


def test_cannot_remove_last_object_slot():
    _, editor = _build_editor()

    editor.add_object_slot()
    editor.add_object_slot()

    editor.remove_object_slot("armor")
    editor.remove_object_slot("utility")
    editor.remove_object_slot("weapon")

    assert editor._active_object_keys == ["weapon"]


def test_add_object_slot_activates_objects_in_order():
    _, editor = _build_editor()

    assert editor._active_object_keys == ["weapon"]

    editor.add_object_slot()
    editor.add_object_slot()

    assert editor._active_object_keys == ["weapon", "armor", "utility"]


def test_add_object_slot_after_third_creates_new_row_with_new_object():
    _, editor = _build_editor()

    editor.add_object_slot()
    editor.add_object_slot()
    editor.add_object_slot()

    assert editor._active_object_keys == ["weapon", "armor", "utility", "object_4"]
    assert editor._columns["object_4"]["box"]._grid_kwargs["row"] == 2
    assert editor._columns["object_4"]["box"]._grid_kwargs["column"] == 0
    assert len(editor._columns["object_4"]["rows"]) == 1

def test_apply_payload_restores_dynamic_object_slots_from_saved_draft():
    _, editor = _build_editor(max_level=4)

    editor.apply_payload(
        equipment={
            "weapon": "Lame",
            "object_4": "Totem",
        },
        purchases={
            "weapon": {"damage": 1, "pierce_armor": 0, "special_effect": 0, "skill_bonus": 0},
            "object_4": {
                "damage": 0,
                "pierce_armor": 0,
                "armor": 0,
                "special_effect": 2,
                "skill_bonus": 0,
            },
        },
    )

    assert "object_4" in editor._columns
    assert "object_4" in editor._active_object_keys
    assert editor.get_equipment_names()["object_4"] == "Totem"
    assert editor.get_purchase_payload()["object_4"]["special_effect"] == 2
