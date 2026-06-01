"""Regression tests for the character creation skill dice display."""

import sys
import tkinter as tk
import types

import pytest


class _DummyWidget:
    def __init__(self, master=None, *args, **kwargs):
        """Initialize the _DummyWidget instance."""
        self.master = master
        self._children = []
        if hasattr(master, "_children"):
            master._children.append(self)

    def grid(self, *args, **kwargs):
        """Handle grid."""
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        """Handle grid columnconfigure."""
        return None

    def destroy(self):
        """Handle destroy."""
        return None

    def winfo_children(self):
        """Handle winfo children."""
        return list(self._children)


@pytest.fixture(scope="module")
def character_creation_view_cls(request):
    """Import the view under a local customtkinter stub."""
    ctk_stub = types.SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkComboBox=_DummyWidget,
        CTkEntry=_DummyWidget,
        CTkCheckBox=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkScrollableFrame=_DummyWidget,
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(sys.modules, "customtkinter", ctk_stub)
    request.addfinalizer(monkeypatch.undo)
    sys.modules.pop("modules.pcs.character_creation.view", None)

    from modules.pcs.character_creation.view import CharacterCreationView

    try:
        yield CharacterCreationView
    finally:
        sys.modules.pop("modules.pcs.character_creation.view", None)


from modules.pcs.character_creation.progression import ADVANCEMENT_OPTIONS


def test_skill_die_display_tracks_base_bonus_and_advancement_effects(character_creation_view_cls):
    """Verify that skill die labels include advancement effects in their totals."""
    root = tk.Tcl()
    view = character_creation_view_cls.__new__(character_creation_view_cls)
    view.inputs = {"advancements": tk.StringVar(master=root, value="1")}
    view.favorite_vars = {
        "Combat": tk.BooleanVar(master=root, value=True),
        "Perception": tk.BooleanVar(master=root, value=True),
    }
    view.skill_vars = {
        "Combat": tk.StringVar(master=root, value="1"),
        "Perception": tk.StringVar(master=root, value="0"),
    }
    view.bonus_skill_vars = {
        "Combat": tk.StringVar(master=root, value="0"),
        "Perception": tk.StringVar(master=root, value="4"),
    }
    view.skill_die_vars = {
        "Combat": tk.StringVar(master=root, value=""),
        "Perception": tk.StringVar(master=root, value=""),
    }
    view.advancement_rows = [
        {
            "type_var": tk.StringVar(master=root, value="skill_improvement"),
            "details_var": tk.StringVar(master=root, value="Combat, Perception"),
        }
    ]

    view._update_skill_dice_markers()

    assert view.skill_die_vars["Combat"].get() == "d6"
    assert view.skill_die_vars["Perception"].get() == "d12"

    view.skill_vars["Combat"].set("5")
    view._update_skill_dice_markers()

    assert view.skill_die_vars["Combat"].get() == "d12+1"


def test_advancement_details_change_refreshes_skill_die_display_via_live_callback(character_creation_view_cls):
    """Verify that changing advancement details refreshes the dice display through the live callback."""
    root = tk.Tcl()
    view = character_creation_view_cls.__new__(character_creation_view_cls)
    view.inputs = {"advancements": tk.StringVar(master=root, value="1")}
    view.favorite_vars = {
        "Combat": tk.BooleanVar(master=root, value=True),
        "Perception": tk.BooleanVar(master=root, value=True),
    }
    view.skill_vars = {
        "Combat": tk.StringVar(master=root, value="1"),
        "Perception": tk.StringVar(master=root, value="1"),
    }
    view.bonus_skill_vars = {
        "Combat": tk.StringVar(master=root, value="0"),
        "Perception": tk.StringVar(master=root, value="0"),
    }
    view.skill_die_vars = {
        "Combat": tk.StringVar(master=root, value="-"),
        "Perception": tk.StringVar(master=root, value="-"),
    }
    view.advancement_frame = _DummyWidget()
    view.advancement_frame.tk = root
    view.advancement_rows = []
    view._advancement_choices_cache = [{"type": "skill_improvement", "details": ""}]
    view.prowess_editor = types.SimpleNamespace(get_payload=lambda: [])
    view.feat_count_var = tk.StringVar(master=root, value="")
    view.prowess_points_var = tk.StringVar(master=root, value="")
    view.skills_header_var = tk.StringVar(master=root, value="")
    view._render_feat_rows = lambda *_args, **_kwargs: None
    view._update_remaining_points_marker = lambda *_args, **_kwargs: None
    view._update_equipment_points_marker = lambda *_args, **_kwargs: None

    view._render_advancement_rows()
    view._update_skill_dice_markers()
    assert view.skill_die_vars["Combat"].get() == "d4"
    assert view.skill_die_vars["Perception"].get() == "d4"

    option_label_map = {value: label for value, label in ADVANCEMENT_OPTIONS}
    view.advancement_rows[0]["type_var"].set("equipment_points")
    assert view.advancement_rows[0]["label_var"].get() == option_label_map["equipment_points"]
    view.advancement_rows[0]["type_var"].set("skill_improvement")

    view.advancement_rows[0]["details_var"].set("Combat, Perception")

    assert view.skill_die_vars["Combat"].get() == "d6"
    assert view.skill_die_vars["Perception"].get() == "d6"


def test_advancement_count_change_refreshes_skill_die_display_after_rows_rebuild(character_creation_view_cls):
    """Verify that changing the advancement count refreshes the dice display after row rebuild."""
    root = tk.Tcl()
    view = character_creation_view_cls.__new__(character_creation_view_cls)
    view.inputs = {"advancements": tk.StringVar(master=root, value="1")}
    view.favorite_vars = {
        "Combat": tk.BooleanVar(master=root, value=True),
        "Perception": tk.BooleanVar(master=root, value=True),
    }
    view.skill_vars = {
        "Combat": tk.StringVar(master=root, value="1"),
        "Perception": tk.StringVar(master=root, value="0"),
    }
    view.bonus_skill_vars = {
        "Combat": tk.StringVar(master=root, value="0"),
        "Perception": tk.StringVar(master=root, value="4"),
    }
    view.skill_die_vars = {
        "Combat": tk.StringVar(master=root, value="-"),
        "Perception": tk.StringVar(master=root, value="-"),
    }
    view.advancement_frame = _DummyWidget()
    view.advancement_frame.tk = root
    view.advancement_rows = [
        {
            "type_var": tk.StringVar(master=root, value="skill_improvement"),
            "details_var": tk.StringVar(master=root, value="Combat, Perception"),
        }
    ]
    view._advancement_choices_cache = []
    view.prowess_editor = types.SimpleNamespace(get_payload=lambda: [])
    view.feat_count_var = tk.StringVar(master=root, value="")
    view.prowess_points_var = tk.StringVar(master=root, value="")
    view.skills_header_var = tk.StringVar(master=root, value="")
    view._render_feat_rows = lambda *_args, **_kwargs: None
    view._update_remaining_points_marker = lambda *_args, **_kwargs: None
    view._update_equipment_points_marker = lambda *_args, **_kwargs: None

    view.inputs["advancements"].trace_add("write", view._on_advancements_changed)
    view.inputs["advancements"].set("2")

    assert view.skill_die_vars["Combat"].get() == "d6"
    assert view.skill_die_vars["Perception"].get() == "d12"


def test_apply_payload_refreshes_skill_die_display(character_creation_view_cls):
    """Verify that applying a payload refreshes the dice label."""
    root = tk.Tcl()
    view = character_creation_view_cls.__new__(character_creation_view_cls)
    view.inputs = {
        "name": tk.StringVar(master=root, value=""),
        "player": tk.StringVar(master=root, value=""),
        "concept": tk.StringVar(master=root, value=""),
        "flaw": tk.StringVar(master=root, value=""),
        "group_asset": tk.StringVar(master=root, value=""),
        "advancements": tk.StringVar(master=root, value="0"),
    }
    view.favorite_vars = {"Combat": tk.BooleanVar(master=root, value=False)}
    view.skill_vars = {"Combat": tk.StringVar(master=root, value="0")}
    view.bonus_skill_vars = {"Combat": tk.StringVar(master=root, value="0")}
    view.skill_die_vars = {"Combat": tk.StringVar(master=root, value="-")}
    view.advancement_rows = []
    view._render_advancement_rows = lambda: None
    view._render_feat_rows = lambda *_args, **_kwargs: None
    view._update_remaining_points_marker = lambda *_args, **_kwargs: None
    view._update_equipment_points_marker = lambda *_args, **_kwargs: None
    view.equipment_editor = types.SimpleNamespace(apply_payload=lambda *_args, **_kwargs: None)

    view._apply_payload(
        {
            "name": "Alya",
            "player": "Unit",
            "concept": "Rogue",
            "flaw": "Impulsive",
            "group_asset": "Safehouse",
            "advancements": 0,
            "favorites": ["Combat"],
            "skills": {"Combat": 3},
            "bonus_skills": {"Combat": 2},
            "feats": [],
            "equipment": {"weapon": "Dague", "armor": "Veste", "utility": "Outils"},
            "equipment_purchases": {},
            "equipment_pe": {"weapon": 0, "armor": 0, "utility": 0},
            "advancement_choices": [],
        }
    )

    assert view.inputs["name"].get() == "Alya"
    assert view.skill_die_vars["Combat"].get() == "d12"
