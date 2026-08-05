"""Tests for GM Table scenario board data and integration."""

from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.gm_table.scenario_board import (
    build_scenario_board_data,
    normalize_list_field,
    resolve_scenario_bundle,
    split_scene_title,
)
from modules.helpers import theme_manager
from modules.scenarios.gm_table.scenario_board.styles import (
    resolve_scenario_board_palette,
)
from modules.scenarios.gm_table.panel_skins import readable_text_color
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


def test_build_scenario_board_data_prepares_reference_sheet_directives() -> None:
    """Dense board bands accept both current and legacy scenario field names."""
    data = build_scenario_board_data(
        {
            "MainObjective": "Reach the flooded clinic.",
            "Stakes": "The suspect escapes at dawn.",
            "Route": "Checkpoint → Refuge → Clinic → Train",
        }
    )

    assert data.objective == "Reach the flooded clinic."
    assert data.pressure == "The suspect escapes at dawn."
    assert data.checkpoint == "Checkpoint → Refuge → Clinic → Train"


def test_build_scenario_board_data_accepts_plural_objectives_field() -> None:
    """The objectives band should support the plural template field name."""
    data = build_scenario_board_data({"Objectives": "Rescue the archivist."})

    assert data.objective == "Rescue the archivist."


def test_scenario_board_displays_objective_only_in_reference_band() -> None:
    """The compact directive row must not repeat the objective reference band."""
    from modules.scenarios.gm_table.scenario_board.content import (
        build_directives,
        build_info_bands,
    )

    data = build_scenario_board_data(
        {
            "Objectives": "Rescue the archivist.",
            "Secrets": "The archive is compromised.",
            "Stakes": "The evidence will be destroyed.",
        }
    )

    assert build_info_bands(data)[0] == (
        "OBJECTIVES",
        (),
        "Rescue the archivist.",
    )
    assert build_directives(data) == (
        ("SECRET", "The archive is compromised.", "secret"),
        ("PRESSURE", "The evidence will be destroyed.", "pressure"),
    )


def test_scenario_board_info_band_displays_villains_with_major_npcs() -> None:
    """Villains belong with major NPCs without leaking into the creature band."""
    from modules.scenarios.gm_table.scenario_board.content import (
        ENTITY_ACTIONS,
        build_info_bands,
    )

    data = build_scenario_board_data(
        {
            "NPCs": ["Captain Vale"],
            "Villains": ["The Fox"],
            "Creatures": ["Cave Drake"],
        }
    )

    creature_band = build_info_bands(data)[2]
    major_npc_band = build_info_bands(data)[1]

    assert major_npc_band == (
        "MAJOR NPCS",
        (("NPCs", "Captain Vale"), ("Villains", "The Fox")),
        "",
    )
    assert creature_band == (
        "CREATURES",
        (("Creatures", "Cave Drake"),),
        "",
    )
    assert ("Open Creatures", "Creatures") in ENTITY_ACTIONS
    assert all(entity_type != "Villains" for _label, entity_type in ENTITY_ACTIONS)


def test_scenario_board_reference_content_uses_regular_weight(monkeypatch) -> None:
    """Reference headings are bold without making their content bold too."""
    from modules.scenarios.gm_table.scenario_board import entity_links, page

    widgets = []

    class _Widget:
        def __init__(self, master=None, **kwargs):
            self.master = master
            self.options = kwargs
            widgets.append(self)

        def grid(self, **_kwargs):
            return None

        def pack(self, **_kwargs):
            return None

        def bind(self, *_args, **_kwargs):
            return None

        def configure(self, **kwargs):
            self.options.update(kwargs)

    monkeypatch.setattr(page.ctk, "CTkFrame", _Widget)
    monkeypatch.setattr(page.ctk, "CTkLabel", _Widget)
    monkeypatch.setattr(page.ctk, "CTkFont", lambda **kwargs: kwargs)
    monkeypatch.setattr(entity_links.ctk, "CTkButton", _Widget)
    monkeypatch.setattr(entity_links.ctk, "CTkLabel", _Widget)
    monkeypatch.setattr(entity_links.ctk, "CTkFont", lambda **kwargs: kwargs)

    panel = object.__new__(page.ScenarioBoardPanel)
    panel._data = build_scenario_board_data(
        {
            "Objectives": "Reach the throne.",
            "NPCs": ["Lysandra Malrec"],
            "Villains": ["The Red Queen"],
        }
    )
    panel._palette = SimpleNamespace(
        info_bands=("#111111",) * 5,
        info_band_text_colors=("#FFFFFF",) * 5,
        border="#333333",
        text="#FFFFFF",
        villain_text="#FF5C5C",
        control_hover="#222222",
    )
    panel._open_entity_callback = None

    panel._add_info_bands(_Widget(), 0)

    heading = next(
        widget for widget in widgets if widget.options.get("text") == "OBJECTIVES"
    )
    objective = next(
        widget
        for widget in widgets
        if widget.options.get("text") == "Reach the throne."
    )
    npc = next(
        widget for widget in widgets if widget.options.get("text") == "Lysandra Malrec"
    )
    villain = next(
        widget for widget in widgets if widget.options.get("text") == "The Red Queen"
    )

    assert heading.options["font"] == {"size": 11, "weight": "bold"}
    assert objective.options["font"] == {"size": 13}
    assert npc.options["font"] == {"size": 13, "underline": True}
    assert npc.options["text_color"] == "#FFFFFF"
    assert villain.options["font"] == {"size": 13, "underline": True}
    assert villain.options["text_color"] == "#FF5C5C"


def test_full_width_wrap_uses_parent_width_without_configure_feedback() -> None:
    """Wrapping must not bind to the label and continuously resize itself."""
    from modules.scenarios.gm_table.scenario_board.entity_links import (
        bind_full_width_wrap,
    )

    class _Parent:
        def bind(self, event_name, callback, *, add):
            self.binding = (event_name, callback, add)

    class _Label:
        def __init__(self):
            self.master = _Parent()
            self.wraplengths = []

        def bind(self, *_args, **_kwargs):
            raise AssertionError("the resizable label must not observe itself")

        def configure(self, *, wraplength):
            self.wraplengths.append(wraplength)

    label = _Label()
    bind_full_width_wrap(label, padding=14, initial_wraplength=240)

    assert label.wraplengths == [240]

    event_name, callback, add = label.master.binding
    assert (event_name, add) == ("<Configure>", "+")
    callback(SimpleNamespace(width=300))
    callback(SimpleNamespace(width=300))
    callback(SimpleNamespace(width=360))

    assert label.wraplengths == [240, 286, 346]


def test_scene_grid_layout_fills_incomplete_final_rows() -> None:
    """The last row must use the full board instead of narrow empty columns."""
    from modules.scenarios.gm_table.scenario_board.layout import (
        build_scene_grid_layout,
    )

    five_scenes = build_scene_grid_layout(5)
    assert [(cell.row, cell.column, cell.columnspan) for cell in five_scenes] == [
        (0, 0, 5),
        (0, 5, 5),
        (0, 10, 5),
        (0, 15, 5),
        (1, 0, 20),
    ]

    seven_scenes = build_scene_grid_layout(7)
    assert [(cell.row, cell.column, cell.columnspan) for cell in seven_scenes[4:]] == [
        (1, 0, 7),
        (1, 7, 7),
        (1, 14, 6),
    ]


def test_initial_scene_wraplength_scales_with_card_span() -> None:
    """A card gets a deterministic wrap width before its first resize event."""
    from modules.scenarios.gm_table.scenario_board.layout import (
        initial_scene_wraplength,
    )

    assert initial_scene_wraplength(5) == 211
    assert initial_scene_wraplength(20) == 886


def test_scenario_board_rejects_non_positive_scene_state() -> None:
    """Persisted scene selection must continue to reject invalid indices."""
    from modules.scenarios.gm_table.scenario_board.page import ScenarioBoardPanel

    assert ScenarioBoardPanel._coerce_scene_index(-1) is None
    assert ScenarioBoardPanel._coerce_scene_index(0) is None
    assert ScenarioBoardPanel._coerce_scene_index("2") == 2


def test_scenario_board_has_dedicated_default_panel_size() -> None:
    """The scenario board should open as a large planning panel."""
    assert resolve_default_panel_size("scenario_board") == (900, 680)


def test_info_band_titles_use_readable_text_for_each_background() -> None:
    """Reference-band headings must remain legible across every app theme."""
    for theme in ("default", "medieval", "sf"):
        palette = resolve_scenario_board_palette(theme)

        assert palette.info_band_text_colors == tuple(
            readable_text_color(background) for background in palette.info_bands
        )


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


def test_open_scene_map_shows_only_linked_map_choices(monkeypatch) -> None:
    """Open Scene Map should present only the current bundle's linked maps."""
    from modules.scenarios.gm_table.scenario_board import page

    opened = []
    button_labels = []

    class _Toplevel:
        def __init__(self, _master):
            self.destroyed = False

        def title(self, _value):
            pass

        def geometry(self, _value):
            pass

        def transient(self, _value):
            pass

        def grab_set(self):
            pass

        def destroy(self):
            self.destroyed = True

    class _Widget:
        def __init__(self, master=None, **kwargs):
            self.master = master
            self.options = kwargs
            text = kwargs.get("text")
            if text and text not in {"Choose a linked map to open:", "Cancel"}:
                button_labels.append(text)

        def pack(self, **_kwargs):
            return None

    monkeypatch.setattr(page.ctk, "CTkToplevel", _Toplevel)
    monkeypatch.setattr(page.ctk, "CTkLabel", _Widget)
    monkeypatch.setattr(page.ctk, "CTkScrollableFrame", _Widget)
    monkeypatch.setattr(page.ctk, "CTkButton", _Widget)
    monkeypatch.setattr(page.ctk, "CTkFont", lambda **kwargs: kwargs)

    panel = object.__new__(page.ScenarioBoardPanel)
    panel._palette = SimpleNamespace(
        text="#FFFFFF",
        background="#111111",
        control="#222222",
        control_hover="#333333",
        control_text="#EEEEEE",
        surface="#444444",
    )
    panel._open_scene_map_callback = opened.append
    panel.winfo_toplevel = lambda: None

    panel._open_scene_map_picker(("Gallery Map", "Vault Map"))

    assert button_labels == ["Gallery Map", "Vault Map"]
    assert opened == []


def test_open_current_scene_map_opens_single_map_without_picker() -> None:
    """A single linked map should open directly without forcing a picker."""
    from modules.scenarios.gm_table.scenario_board import page

    opened = []
    panel = object.__new__(page.ScenarioBoardPanel)
    panel._open_scene_map_callback = opened.append
    panel._current_bundle = lambda: SimpleNamespace(maps=(" Gallery Map ", "gallery map"))
    panel._open_scene_map_picker = lambda _map_names: opened.append("picker")

    panel._open_current_scene_map()

    assert opened == ["Gallery Map"]


def test_select_scene_map_opens_chosen_linked_map() -> None:
    """Choosing from the linked-map picker should open that exact map."""
    from modules.scenarios.gm_table.scenario_board import page

    opened = []
    selector = SimpleNamespace(destroyed=False)
    selector.destroy = lambda: setattr(selector, "destroyed", True)
    panel = object.__new__(page.ScenarioBoardPanel)
    panel._open_scene_map_callback = opened.append

    panel._select_scene_map(selector, "Vault Map")

    assert selector.destroyed is True
    assert opened == ["Vault Map"]

def test_scenario_board_palette_follows_application_themes() -> None:
    """Board surfaces and controls should come from each application theme."""
    palettes = {}
    for theme in (
        theme_manager.THEME_DEFAULT,
        theme_manager.THEME_MEDIEVAL,
        theme_manager.THEME_SF,
    ):
        tokens = theme_manager.get_tokens(theme)
        palette = resolve_scenario_board_palette(theme)
        palettes[theme] = palette

        assert palette.background == tokens["panel_bg"]
        assert palette.surface == tokens["panel_alt_bg"]
        assert palette.control == tokens["accent_button_fg"]
        assert palette.control_hover == tokens["accent_button_hover"]
        assert len(palette.info_bands) == 5
        assert len(palette.scene_colors) == 4

    assert len({palette.background for palette in palettes.values()}) == 3
    assert len({palette.scene_colors for palette in palettes.values()}) == 3
