"""Tests for GM Table scenario board data and integration."""

from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.gm_table.scenario_board import (
    build_scenario_board_data,
    normalize_list_field,
    resolve_scenario_bundle,
    split_scene_title,
)
from modules.scenarios.gm_table.workspace import resolve_default_panel_size
from modules.scenarios.gm_table_view import GMTableView


def test_normalize_list_field_accepts_json_lines_and_dicts() -> None:
    """Scenario board fields can come from templates, JSON, or hydrated records."""
    assert normalize_list_field('["A", "B"]') == ("A", "B")
    assert normalize_list_field("A\n\nB") == ("A", "B")
    assert normalize_list_field([{"Title": "Scene NPC"}, {"Name": "Legacy NPC"}]) == (
        "Scene NPC",
        "Legacy NPC",
    )


def test_split_scene_title_uses_first_short_line_as_card_title() -> None:
    """Scene cards should get a readable title without losing body text."""
    title, body = split_scene_title("Warehouse Ambush\nKey beats:\n- Alarm", 2)

    assert title == "Warehouse Ambush"
    assert body == "Key beats:\n- Alarm"


def test_build_scenario_board_data_extracts_scenes_sections_and_links() -> None:
    """Board data should normalize scenario metadata for UI rendering."""
    data = build_scenario_board_data(
        {
            "Title": "Night Run",
            "Status": "Ready",
            "Summary": "A chase through the docks.",
            "Secrets": "The patron is lying.",
            "Scenes": [
                "Cold Open\nKey beats:\n- Meet the fixer\nClues/hooks:\n- Blue ticket",
                "Finale: Fight on the ferry",
            ],
            "NPCs": ["Fixer", "Captain"],
            "Places": '["Docks"]',
        }
    )

    assert data.title == "Night Run"
    assert data.status == "Ready"
    assert data.summary == "A chase through the docks."
    assert data.secrets == "The patron is lying."
    assert [scene.title for scene in data.scenes] == ["Cold Open", "Finale"]
    assert data.scenes[0].sections[0]["title"] == "Key beats"
    assert data.scenes[0].sections[0]["items"] == ["Meet the fixer"]
    assert data.linked_entities["NPCs"] == ("Fixer", "Captain")
    assert data.linked_entities["Places"] == ("Docks",)


def test_build_scenario_board_data_decodes_serialized_rich_text_payloads() -> None:
    """Scenario Board should render rich-text payloads as readable plain text."""
    data = build_scenario_board_data(
        {
            "Title": "Payload Run",
            "Summary": "{'text': 'Readable summary.', 'formatting': {'bold': []}}",
            "Secrets": {"text": "Readable secret.", "formatting": {"italic": []}},
            "Scenes": [
                {
                    "Title": "Dict Scene",
                    "Text": "{'text': 'Plain scene body.', 'formatting': {'bold': []}}",
                },
                r'{"text":"Inline Scene\nScene from JSON payload.","formatting":{"italic":[]}}',
            ],
        }
    )

    assert data.summary == "Readable summary."
    assert data.secrets == "Readable secret."
    assert data.scenes[0].body == "Plain scene body."
    assert data.scenes[0].intro_text == "Plain scene body."
    assert data.scenes[1].title == "Inline Scene"
    assert data.scenes[1].body == "Scene from JSON payload."

def test_scenario_board_has_dedicated_default_panel_size() -> None:
    """The scenario board should open as a large planning panel."""
    assert resolve_default_panel_size("scenario_board") == (900, 680)


def test_handle_add_option_routes_scenario_board_to_scenario_picker() -> None:
    """The GM Table add menu should request a scenario before opening the board."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view._open_scenario_selection_for_panel = (
        lambda panel_kind, **kwargs: captured.append((panel_kind, kwargs))
    )

    GMTableView._handle_add_option(view, "Scenario Board")

    assert captured == [("scenario_board", {})]


def test_scenario_selection_creates_scenario_board_panel() -> None:
    """Selected scenarios should create persisted scenario_board panels."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view.wrappers = {"Scenarios": SimpleNamespace()}
    view._templates = {"Scenarios": {}}
    view.winfo_toplevel = lambda: None
    view._entity_label = lambda _entity_type, item, fallback="": item.get(
        "Title", fallback
    )
    view.open_or_focus_scenario_board = (
        lambda scenario_title, **kwargs: captured.append(
            ("scenario_board", scenario_title, kwargs)
        )
    )

    class _Popup:
        def title(self, _value):
            pass

        def geometry(self, _value):
            pass

        def transient(self, _value):
            pass

        def grab_set(self):
            pass

        def focus_force(self):
            pass

        def destroy(self):
            captured.append(("destroy",))

    class _SelectionView:
        def __init__(self, _popup, entity_type, _wrapper, _template, callback):
            assert entity_type == "Scenarios"
            callback("Scenarios", "Fallback", {"Title": "Night Run"})

        def pack(self, **_kwargs):
            pass

    import modules.scenarios.gm_table_view as gm_table_view_module

    original_toplevel = gm_table_view_module.ctk.CTkToplevel
    original_selection = gm_table_view_module.GenericListSelectionView
    try:
        gm_table_view_module.ctk.CTkToplevel = lambda _master: _Popup()
        gm_table_view_module.GenericListSelectionView = _SelectionView
        GMTableView._open_scenario_selection_for_panel(view, "scenario_board")
    finally:
        gm_table_view_module.ctk.CTkToplevel = original_toplevel
        gm_table_view_module.GenericListSelectionView = original_selection

    assert captured == [
        ("destroy",),
        ("scenario_board", "Night Run", {"workspace": None}),
    ]


def test_build_scenario_board_data_extracts_scene_flow_dict_entities() -> None:
    """Scenario Board accepts scene-flow variants and structured scene references."""
    data = build_scenario_board_data(
        {
            "Title": "Museum Job",
            "SceneFlow": {
                "002": {
                    "title": "Gallery Chase",
                    "description": "Run through the exhibits.",
                    "NPCs": ["Curator"],
                    "Villains": "The Fox",
                    "Places": [{"Name": "Grand Gallery"}],
                    "Maps": "Gallery Map",
                }
            },
        }
    )

    assert [scene.title for scene in data.scenes] == ["Gallery Chase"]
    scene = data.scenes[0]
    assert scene.body == "Run through the exhibits."
    assert scene.npcs == ("Curator",)
    assert scene.villains == ("The Fox",)
    assert scene.places == ("Grand Gallery",)
    assert scene.maps == ("Gallery Map",)


def test_resolve_scenario_bundle_uses_scene_and_tolerant_wrapper_matches() -> None:
    """Bundle service resolves scene/scenario candidates using forgiving aliases."""
    scene = build_scenario_board_data(
        {
            "Title": "Museum Job",
            "Scenes": [
                {
                    "Title": "Gallery Chase",
                    "NPCs": ["curator vale"],
                    "Villains": ["THE FOX"],
                    "Places": ["Grand-Gallery"],
                    "Maps": ["gallerymap"],
                }
            ],
        }
    ).scenes[0]
    wrappers = {
        "NPCs": SimpleNamespace(load_items=lambda: [{"Name": "Curator Vale"}]),
        "Villains": SimpleNamespace(load_items=lambda: [{"Name": "The Fox"}]),
        "Places": SimpleNamespace(load_items=lambda: [{"Name": "Grand Gallery"}]),
    }
    map_wrapper = SimpleNamespace(
        load_items=lambda: [
            {"Name": "Gallery Map"},
            {"Name": "Campaign World", "Type": "World Map"},
        ]
    )

    bundle = resolve_scenario_bundle(
        {"Title": "Museum Job", "NPCs": ["Spare Contact"]},
        scene,
        wrappers,
        map_wrapper,
    )

    assert bundle.scenario_title == "Museum Job"
    assert bundle.scene_title == "Gallery Chase"
    assert bundle.npcs == ("Spare Contact", "Curator Vale")
    assert bundle.villains == ("The Fox",)
    assert bundle.places == ("Grand Gallery",)
    assert bundle.maps == ("Gallery Map",)
    assert bundle.world_maps == ("Campaign World",)
