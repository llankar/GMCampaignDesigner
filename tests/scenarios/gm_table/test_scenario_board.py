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
from modules.scenarios.gm_table.scenario_board.character_graph_view import (
    LINK_LABEL_BG_TAG,
    LINK_LABEL_TAG,
    ScenarioBoardCharacterGraph,
)
from modules.characters.character_graph_editor import CharacterGraphEditor
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


def test_build_scenario_board_data_normalizes_saved_character_graph() -> None:
    """Scenario Board exposes wizard graph data even when SQLite returns JSON."""
    data = build_scenario_board_data(
        {
            "Title": "Night Run",
            "ScenarioCharacterGraph": (
                '{"nodes":[{"tag":"npc_fixer","entity_type":"npc",'
                '"entity_name":"Fixer","x":120,"y":160}],"links":[]}'
            ),
        }
    )

    assert data.character_graph["nodes"][0]["entity_name"] == "Fixer"
    assert data.character_graph["links"] == []
    assert data.character_graph["shapes"] == []


def test_build_scenario_board_data_filters_saved_graph_links_without_endpoints() -> None:
    """Saved graph links must never render against missing board nodes."""
    data = build_scenario_board_data(
        {
            "Title": "Mentor Trouble",
            "ScenarioCharacterGraph": {
                "nodes": [
                    {
                        "tag": "npc_lysandra",
                        "entity_type": "npc",
                        "entity_name": "Lysandra Malrec",
                    },
                    {
                        "tag": "npc_mentor",
                        "entity_type": "npc",
                        "entity_name": "Ancien Mentor",
                    },
                ],
                "links": [
                    {
                        "node1_tag": "npc_mentor",
                        "node2_tag": "scene_5",
                        "text": "Scene 5",
                    },
                    {
                        "npc_name1": "Ancien Mentor",
                        "npc_name2": "Lysandra Malrec",
                        "text": "ancien mentor",
                    },
                    {
                        "node1_tag": "npc_lysandra",
                        "node2_tag": "npc_mentor",
                        "text": "Scene 5",
                    },
                ],
            },
        }
    )

    node_tags = {node["tag"] for node in data.character_graph["nodes"]}

    assert node_tags == {"npc_lysandra", "npc_mentor"}
    assert data.character_graph["links"] == [
        {
            "node1_tag": "npc_lysandra",
            "node2_tag": "npc_mentor",
            "text": "ancien mentor / Scene 5",
            "arrow_mode": "both",
        }
    ]
    assert all(
        link["node1_tag"] in node_tags and link["node2_tag"] in node_tags
        for link in data.character_graph["links"]
    )


def test_build_scenario_board_data_preserves_directional_saved_graph_link_order() -> None:
    """Pair-level label merging must not reverse a directional graph link."""
    data = build_scenario_board_data(
        {
            "ScenarioCharacterGraph": {
                "nodes": [
                    {
                        "tag": "npc_zed",
                        "entity_type": "npc",
                        "entity_name": "Zed",
                    },
                    {
                        "tag": "npc_ada",
                        "entity_type": "npc",
                        "entity_name": "Ada",
                    },
                ],
                "links": [
                    {
                        "node1_tag": "npc_zed",
                        "node2_tag": "npc_ada",
                        "text": "orders",
                        "arrow_mode": "end",
                    },
                    {
                        "node1_tag": "npc_ada",
                        "node2_tag": "npc_zed",
                        "text": "reports",
                        "arrow_mode": "start",
                    },
                ],
            },
        }
    )

    assert data.character_graph["links"] == [
        {
            "node1_tag": "npc_zed",
            "node2_tag": "npc_ada",
            "text": "orders / reports",
            "arrow_mode": "end",
        }
    ]


def test_build_scenario_board_data_maps_legacy_link_names_case_and_accent_insensitive() -> None:
    """Legacy npc_name links should resolve to existing nodes by folded names."""
    data = build_scenario_board_data(
        {
            "ScenarioCharacterGraph": {
                "nodes": [
                    {
                        "tag": "npc_elise",
                        "entity_type": "NPCs",
                        "entity_name": "\u00c9lise Montclair",
                    },
                    {
                        "tag": "npc_remy",
                        "entity_type": "npc",
                        "entity_name": "R\u00e9my Solal",
                    },
                ],
                "links": [
                    {
                        "npc_name1": "elise montclair",
                        "npc_name2": "REMY SOLAL",
                        "text": "confides",
                    }
                ],
            },
        }
    )

    assert data.character_graph["links"] == [
        {
            "node1_tag": "npc_elise",
            "node2_tag": "npc_remy",
            "text": "confides",
            "arrow_mode": "both",
        }
    ]


def test_build_scenario_board_data_builds_scene_npc_graph_fallback() -> None:
    """Scenario Board should still show an NPC graph when no saved graph exists."""
    data = build_scenario_board_data(
        {
            "Title": "Museum Job",
            "NPCs": ["Curator Vale", "Rika Vale"],
            "Scenes": [
                {
                    "Title": "Gallery Chase",
                    "NPCs": ["Curator Vale", "Rika Vale"],
                },
                {
                    "Title": "Vault Negotiation",
                    "NPCs": ["Rika Vale", "Broker Kade"],
                },
            ],
        }
    )

    nodes = data.character_graph["nodes"]
    links = data.character_graph["links"]

    assert [node["entity_name"] for node in nodes] == [
        "Curator Vale",
        "Rika Vale",
        "Broker Kade",
    ]
    assert {link["text"] for link in links} == {
        "Gallery Chase",
        "Vault Negotiation",
    }
    assert all(link["arrow_mode"] == "both" for link in links)
    assert all(node["entity_type"] == "npc" for node in nodes)


def test_build_scenario_board_data_builds_npc_graph_from_scene_text_mentions() -> None:
    """Linked scenario NPCs mentioned in free text should create graph links."""
    data = build_scenario_board_data(
        {
            "Title": "Le serment de l'Aube",
            "NPCs": [
                "Lysandra Malrec",
                "Lyanna Solveil",
                "Lucan",
                "Arven",
                "Garde",
            ],
            "Scenes": [
                (
                    "La chapelle de l'aube\n"
                    "Lysandra rejoint Lyanna pres de l'autel brise."
                ),
                (
                    "Le guet exterieur\n"
                    "Lucan avertit Arven pendant que le Garde retient Lysandra."
                ),
            ],
        }
    )

    assert [node["entity_name"] for node in data.character_graph["nodes"]] == [
        "Lysandra Malrec",
        "Lyanna Solveil",
        "Lucan",
        "Arven",
        "Garde",
    ]
    assert {
        (frozenset((link["node1_tag"], link["node2_tag"])), link["text"])
        for link in data.character_graph["links"]
    } >= {
        (
            frozenset(("npc_lysandra_malrec", "npc_lyanna_solveil")),
            "La chapelle de l'aube",
        ),
        (frozenset(("npc_lucan", "npc_arven")), "Le guet exterieur"),
        (frozenset(("npc_lucan", "npc_garde")), "Le guet exterieur"),
        (frozenset(("npc_lysandra_malrec", "npc_lucan")), "Le guet exterieur"),
        (frozenset(("npc_arven", "npc_garde")), "Le guet exterieur"),
        (frozenset(("npc_arven", "npc_lysandra_malrec")), "Le guet exterieur"),
        (frozenset(("npc_garde", "npc_lysandra_malrec")), "Le guet exterieur"),
    }
    node_tags = {node["tag"] for node in data.character_graph["nodes"]}
    assert all(
        link["node1_tag"] in node_tags and link["node2_tag"] in node_tags
        for link in data.character_graph["links"]
    )


def test_build_scenario_board_data_matches_french_role_and_title_aliases() -> None:
    """French role names and titled multi-word NPCs should use useful aliases."""
    data = build_scenario_board_data(
        {
            "Title": "Le portail de l'Aube",
            "NPCs": [
                "Garde du Palais de l'Aube",
                "Lysandra Malrec",
                "Capitaine Valen Ordo",
            ],
            "Scenes": [
                (
                    "Portail scelle\n"
                    "Le Garde bloque Lysandra pendant que Valen ferme le portail."
                )
            ],
        }
    )

    assert [node["entity_name"] for node in data.character_graph["nodes"]] == [
        "Garde du Palais de l'Aube",
        "Lysandra Malrec",
        "Capitaine Valen Ordo",
    ]
    assert {
        frozenset((link["node1_tag"], link["node2_tag"]))
        for link in data.character_graph["links"]
    } == {
        frozenset(("npc_garde_du_palais_de_l_aube", "npc_lysandra_malrec")),
        frozenset(("npc_garde_du_palais_de_l_aube", "npc_capitaine_valen_ordo")),
        frozenset(("npc_lysandra_malrec", "npc_capitaine_valen_ordo")),
    }


def test_build_scenario_board_data_keeps_french_role_aliases_ambiguous() -> None:
    """A role alias shared by multiple linked NPCs should not create edges."""
    data = build_scenario_board_data(
        {
            "Title": "Double garde",
            "NPCs": [
                "Garde du Palais",
                "Garde de Nuit",
                "Lysandra Malrec",
            ],
            "Scenes": [
                "Porte nord\nLe Garde bloque Lysandra."
            ],
        }
    )

    assert data.character_graph == {"nodes": [], "links": [], "shapes": []}


def test_build_scenario_board_data_ignores_ambiguous_npc_first_name_mentions() -> None:
    """Ambiguous first-name mentions should not invent relationship edges."""
    data = build_scenario_board_data(
        {
            "Title": "Split Court",
            "NPCs": ["Lysandra Malrec", "Lysandra Vale", "Lyanna Solveil"],
            "Scenes": [
                (
                    "Audience trouble\n"
                    "Lysandra accuse Lyanna devant le conseil."
                )
            ],
        }
    )

    assert data.character_graph == {"nodes": [], "links": [], "shapes": []}


def test_build_scenario_board_data_matches_npc_mentions_without_accents() -> None:
    """French NPC names should match scene prose even when accents are omitted."""
    data = build_scenario_board_data(
        {
            "Title": "Bal des Masques",
            "NPCs": ["Élise Montclair", "Rémy Solal"],
            "Scenes": [
                (
                    "Le salon rouge\n"
                    "Elise interroge REMY pendant que les invites attendent."
                )
            ],
        }
    )

    assert [node["tag"] for node in data.character_graph["nodes"]] == [
        "npc_elise_montclair",
        "npc_remy_solal",
    ]
    assert {
        frozenset((link["node1_tag"], link["node2_tag"]))
        for link in data.character_graph["links"]
    } == {frozenset(("npc_elise_montclair", "npc_remy_solal"))}


def test_build_scenario_board_data_treats_accent_folded_first_names_as_ambiguous() -> None:
    """Accent variants of the same first-name alias should remain conservative."""
    data = build_scenario_board_data(
        {
            "Title": "Double Cour",
            "NPCs": ["Élise Montclair", "Elise Vale", "Rémy Solal"],
            "Scenes": [
                (
                    "Le salon rouge\n"
                    "Elise rejoint Remy avant l'audience."
                )
            ],
        }
    )

    assert data.character_graph == {"nodes": [], "links": [], "shapes": []}


def test_build_scenario_board_data_skips_french_ligature_title_stopwords() -> None:
    """French title stopwords with ligatures should not hide the true given name."""
    data = build_scenario_board_data(
        {
            "Title": "Chapelle close",
            "NPCs": ["S\u0153ur Marie Solal", "R\u00e9my Solal"],
            "Scenes": [
                (
                    "Nef silencieuse\n"
                    "Marie rejoint Remy derriere les piliers."
                )
            ],
        }
    )

    assert {
        frozenset((link["node1_tag"], link["node2_tag"]))
        for link in data.character_graph["links"]
    } == {frozenset(("npc_soeur_marie_solal", "npc_remy_solal"))}


def test_build_scenario_board_data_skips_fallback_graph_without_relationships() -> None:
    """Fallback graph should not duplicate the NPC list when no scene links exist."""
    data = build_scenario_board_data(
        {
            "Title": "Museum Job",
            "NPCs": ["Curator Vale", "Rika Vale"],
            "Scenes": [
                {
                    "Title": "Solo Briefing",
                    "NPCs": ["Curator Vale"],
                },
            ],
        }
    )

    assert data.character_graph == {"nodes": [], "links": [], "shapes": []}


def test_build_scenario_board_data_keeps_saved_graph_before_fallback() -> None:
    """A hand-authored ScenarioCharacterGraph remains the board source of truth."""
    data = build_scenario_board_data(
        {
            "NPCs": ["Curator Vale", "Rika Vale"],
            "Scenes": [
                {
                    "Title": "Gallery Chase",
                    "NPCs": ["Curator Vale", "Rika Vale"],
                },
            ],
            "ScenarioCharacterGraph": {
                "nodes": [
                    {
                        "tag": "npc_curator",
                        "entity_type": "npc",
                        "entity_name": "Curator Vale",
                    }
                ],
                "links": [],
                "shapes": [],
            },
        }
    )

    assert data.character_graph["nodes"] == [
        {
            "tag": "npc_curator",
            "entity_type": "npc",
            "entity_name": "Curator Vale",
        }
    ]
    assert data.character_graph["links"] == []


def test_build_scenario_board_data_discards_malformed_graph_entries() -> None:
    """Malformed persisted graph values must not crash the graph renderer."""
    data = build_scenario_board_data(
        {
            "ScenarioCharacterGraph": {
                "nodes": [None, "not-a-node", {"entity_name": "Fixer"}],
                "links": "not-a-list",
                "shapes": [42],
            }
        }
    )

    assert data.character_graph == {
        "nodes": [
            {
                "entity_name": "Fixer",
                "entity_type": "npc",
                "tag": "npc_Fixer",
            }
        ],
        "links": [],
        "shapes": [],
    }


def test_scenario_board_skips_graph_section_when_saved_graph_has_no_links(
    monkeypatch,
) -> None:
    """Nodes alone are not useful on the Scenario Board relationship strip."""
    from modules.scenarios.gm_table.scenario_board import page

    renderer_calls = []
    frame_calls = []
    panel = object.__new__(page.ScenarioBoardPanel)
    panel._data = SimpleNamespace(
        character_graph={
            "nodes": [{"tag": "npc_fixer", "entity_name": "Fixer"}],
            "links": [],
            "shapes": [],
        }
    )

    monkeypatch.setattr(
        page,
        "create_scenario_character_graph",
        lambda *_args, **_kwargs: renderer_calls.append(True),
    )
    monkeypatch.setattr(
        page.ctk,
        "CTkFrame",
        lambda *_args, **_kwargs: frame_calls.append(True),
    )

    assert panel._add_character_graph(object(), 4) == 4
    assert renderer_calls == []
    assert frame_calls == []


def test_scenario_board_skips_graph_section_when_saved_links_are_filtered(
    monkeypatch,
) -> None:
    """Invalid persisted endpoints should not leave an empty graph section behind."""
    from modules.scenarios.gm_table.scenario_board import page

    data = build_scenario_board_data(
        {
            "ScenarioCharacterGraph": {
                "nodes": [
                    {"tag": "npc_a", "entity_type": "npc", "entity_name": "A"},
                    {"tag": "npc_b", "entity_type": "npc", "entity_name": "B"},
                ],
                "links": [
                    {
                        "node1_tag": "npc_a",
                        "node2_tag": "npc_missing",
                        "text": "Broken",
                    }
                ],
            }
        }
    )
    renderer_calls = []
    frame_calls = []
    panel = object.__new__(page.ScenarioBoardPanel)
    panel._data = data

    monkeypatch.setattr(
        page,
        "create_scenario_character_graph",
        lambda *_args, **_kwargs: renderer_calls.append(True),
    )
    monkeypatch.setattr(
        page.ctk,
        "CTkFrame",
        lambda *_args, **_kwargs: frame_calls.append(True),
    )

    assert data.character_graph["nodes"]
    assert data.character_graph["links"] == []
    assert panel._add_character_graph(object(), 2) == 2
    assert renderer_calls == []
    assert frame_calls == []


def test_scenario_board_renders_graph_section_with_valid_saved_link(
    monkeypatch,
) -> None:
    """A saved graph with at least one drawable relationship still renders."""
    from modules.scenarios.gm_table.scenario_board import page

    class _Section:
        instances = []

        def __init__(self, master=None, **kwargs):
            self.master = master
            self.options = kwargs
            self.grid_calls = []
            self.destroyed = False
            _Section.instances.append(self)

        def grid(self, **kwargs):
            self.grid_calls.append(kwargs)

        def grid_propagate(self, value):
            self.grid_propagate_value = value

        def grid_rowconfigure(self, index, **kwargs):
            self.rowconfigure = (index, kwargs)

        def grid_columnconfigure(self, index, **kwargs):
            self.columnconfigure = (index, kwargs)

        def destroy(self):
            self.destroyed = True

    class _Graph:
        def __init__(self):
            self.grid_calls = []

        def grid(self, **kwargs):
            self.grid_calls.append(kwargs)

    graph_data = {
        "nodes": [
            {"tag": "npc_a", "entity_type": "npc", "entity_name": "A"},
            {"tag": "npc_b", "entity_type": "npc", "entity_name": "B"},
        ],
        "links": [{"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "Scene"}],
        "shapes": [],
    }
    graph = _Graph()
    renderer_calls = []
    panel = object.__new__(page.ScenarioBoardPanel)
    panel._data = SimpleNamespace(character_graph=graph_data)
    panel._wrappers = {}
    panel._palette = SimpleNamespace(surface="#111111", border="#222222")

    def _create_graph(master, *, graph_data, wrappers):
        renderer_calls.append((master, graph_data, wrappers))
        return graph

    monkeypatch.setattr(page.ctk, "CTkFrame", _Section)
    monkeypatch.setattr(page, "create_scenario_character_graph", _create_graph)

    assert panel._add_character_graph(object(), 7) == 8
    assert len(_Section.instances) == 1
    assert renderer_calls == [(_Section.instances[0], graph_data, {})]
    assert graph.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert panel._character_graph is graph


def test_scenario_board_character_graph_blocks_editing_gestures() -> None:
    """The embedded graph is inspectable without exposing record editing actions."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)

    assert graph.on_right_click(None) == "break"
    assert graph.open_character_editor(None) == "break"


class _LinkLabelCanvas:
    def __init__(self, text_bbox):
        self.line_id = 7
        self.arrow_id = 8
        self.text_id = 42
        self.background_id = 99
        self._text_bbox = text_bbox
        self.tags = {self.text_id: {"link_text"}}
        self.rectangles = []
        self.coords_calls = []
        self.itemconfigs = []
        self.lowered = []
        self.raised = []

    def addtag_withtag(self, tag, item_id):
        self.tags.setdefault(item_id, set()).add(tag)

    def bbox(self, item_id):
        assert item_id == self.text_id
        return self._text_bbox

    def create_rectangle(self, *coords, **kwargs):
        self.rectangles.append({"coords": coords, "kwargs": kwargs})
        self.tags[self.background_id] = set(kwargs.get("tags", ()))
        return self.background_id

    def coords(self, item_id, *coords):
        self.coords_calls.append((item_id, coords))

    def itemconfig(self, item_id, **kwargs):
        self.itemconfigs.append((item_id, kwargs))

    def tag_lower(self, item_id, below_id):
        self.lowered.append((item_id, below_id))

    def tag_raise(self, item_id):
        self.raised.append(item_id)


class _MovingLinkCanvas:
    def __init__(self):
        self._next_id = 1
        self.coords_by_id = {}
        self.kwargs_by_id = {}
        self.tags = {}
        self.deleted = []
        self.itemconfigs = []
        self.lowered = []

    def _new_id(self, tags=(), kwargs=None):
        item_id = self._next_id
        self._next_id += 1
        self.tags[item_id] = set(tags)
        self.kwargs_by_id[item_id] = dict(kwargs or {})
        return item_id

    def create_line(self, *coords, **kwargs):
        item_id = self._new_id(kwargs.get("tags", ()), kwargs)
        self.coords_by_id[item_id] = tuple(coords)
        return item_id

    def create_text(self, x, y, **kwargs):
        item_id = self._new_id(kwargs.get("tags", ()), kwargs)
        self.coords_by_id[item_id] = (x, y)
        return item_id

    def create_polygon(self, *coords, **kwargs):
        item_id = self._new_id(kwargs.get("tags", ()), kwargs)
        self.coords_by_id[item_id] = tuple(coords)
        return item_id

    def create_rectangle(self, *coords, **kwargs):
        item_id = self._new_id(kwargs.get("tags", ()), kwargs)
        self.coords_by_id[item_id] = tuple(coords)
        return item_id

    def coords(self, item_id, *coords):
        if coords:
            self.coords_by_id[item_id] = tuple(coords)
        return self.coords_by_id[item_id]

    def itemconfig(self, item_id, **kwargs):
        self.itemconfigs.append((item_id, kwargs))
        self.kwargs_by_id.setdefault(item_id, {}).update(kwargs)

    def delete(self, item_id):
        self.deleted.append(item_id)

    def bbox(self, item_id):
        x, y = self.coords_by_id[item_id][:2]
        return (x - 20, y - 6, x + 20, y + 6)

    def addtag_withtag(self, tag, item_id):
        self.tags.setdefault(item_id, set()).add(tag)

    def tag_lower(self, item_id, below_id=None):
        self.lowered.append((item_id, below_id))


def test_scenario_board_character_graph_label_background_uses_text_bbox() -> None:
    """Link label backgrounds are padded from the rendered text bbox and tagged together."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas = _LinkLabelCanvas((100, 50, 160, 64))
    link = {"node1_tag": "npc_a", "node2_tag": "npc_b"}
    link_key = ScenarioBoardCharacterGraph._link_canvas_key(graph, link)
    graph.link_canvas_ids = {
        link_key: {
            "line": graph.canvas.line_id,
            "arrows": [graph.canvas.arrow_id],
            "text": graph.canvas.text_id,
        }
    }
    graph.selected_link = None

    background_id = ScenarioBoardCharacterGraph._create_link_label_background(
        graph,
        link,
        "npc_a",
        "npc_b",
        graph.canvas.text_id,
    )

    label_item_tag = ScenarioBoardCharacterGraph._link_label_item_tag(
        graph, link, "npc_a", "npc_b"
    )
    assert background_id == graph.canvas.background_id
    assert graph.canvas.rectangles[0]["coords"] == (95, 47, 165, 67)
    assert graph.link_canvas_ids[link_key]["text_bg"] == background_id
    assert {LINK_LABEL_TAG, label_item_tag}.issubset(graph.canvas.tags[graph.canvas.text_id])
    assert {"link", LINK_LABEL_BG_TAG, LINK_LABEL_TAG, label_item_tag}.issubset(
        graph.canvas.tags[background_id]
    )
    assert graph.canvas.lowered == [
        (graph.canvas.line_id, background_id),
        (graph.canvas.arrow_id, background_id),
        (background_id, graph.canvas.text_id),
    ]
    assert graph.canvas.raised == []


def test_scenario_board_character_graph_syncs_label_background_to_text() -> None:
    """Dragging a node updates the stored background rectangle from the moved text bbox."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas = _LinkLabelCanvas((200, 80, 250, 94))
    link = {"node1_tag": "npc_a", "node2_tag": "npc_b"}
    link_key = ScenarioBoardCharacterGraph._link_canvas_key(graph, link)
    graph.link_canvas_ids = {
        link_key: {
            "line": graph.canvas.line_id,
            "arrows": [graph.canvas.arrow_id],
            "text": graph.canvas.text_id,
            "text_bg": graph.canvas.background_id,
        }
    }
    graph.selected_link = None

    ScenarioBoardCharacterGraph._sync_link_label_background(
        graph,
        link,
        "npc_a",
        "npc_b",
    )

    link_color = ScenarioBoardCharacterGraph._get_link_style(graph, link)[0]
    assert graph.canvas.coords_calls == [
        (graph.canvas.background_id, (195, 77, 255, 97))
    ]
    assert graph.canvas.itemconfigs == [
        (graph.canvas.text_id, {"fill": link_color}),
        (graph.canvas.background_id, {"outline": link_color}),
    ]
    assert graph.canvas.lowered == [
        (graph.canvas.line_id, graph.canvas.background_id),
        (graph.canvas.arrow_id, graph.canvas.background_id),
        (graph.canvas.background_id, graph.canvas.text_id),
    ]
    assert graph.canvas.raised == []


def test_scenario_board_character_graph_readable_layout_spaces_nodes() -> None:
    """The board graph replaces compact node coordinates with a wider stable layout."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas_scale = 1.0
    graph.node_positions = {}
    graph.graph = {
        "nodes": [
            {
                "tag": f"npc_{index}",
                "entity_type": "npc",
                "entity_name": f"NPC {index}",
                "x": 200,
                "y": 200,
            }
            for index in range(6)
        ],
        "links": [
            {"node1_tag": "npc_0", "node2_tag": "npc_1", "text": "A"},
            {"node1_tag": "npc_1", "node2_tag": "npc_2", "text": "B"},
            {"node1_tag": "npc_2", "node2_tag": "npc_3", "text": "C"},
            {"node1_tag": "npc_3", "node2_tag": "npc_4", "text": "D"},
            {"node1_tag": "npc_4", "node2_tag": "npc_5", "text": "E"},
        ],
    }

    ScenarioBoardCharacterGraph._apply_readable_board_layout(graph)

    positions = list(graph.node_positions.values())
    assert len(set(positions)) == 6
    for left_index, left in enumerate(positions):
        for right in positions[left_index + 1 :]:
            distance = ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5
            assert distance >= 200
    assert {
        (node["x"], node["y"]) for node in graph.graph["nodes"]
    } == set(positions)
    assert graph.original_positions == graph.node_positions


def test_scenario_board_character_graph_readable_layout_scales_with_node_count() -> None:
    """Ellipse positions should remain usable for small and dense relationship graphs."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas_scale = 1.0

    for count, minimum_distance in ((2, 300), (3, 300), (7, 250), (24, 220)):
        nodes = [
            {"tag": f"npc_{index}", "entity_name": f"NPC {index}"}
            for index in range(count)
        ]
        links = [
            {"node1_tag": f"npc_{index}", "node2_tag": f"npc_{(index + 1) % count}"}
            for index in range(count)
        ]

        positions = list(
            ScenarioBoardCharacterGraph._readable_board_node_positions(
                graph,
                nodes,
                links,
            ).values()
        )

        distances = [
            ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5
            for left_index, left in enumerate(positions)
            for right in positions[left_index + 1 :]
        ]
        assert min(distances) >= minimum_distance


def test_scenario_board_character_graph_preserves_readable_saved_layout() -> None:
    """The board should not overwrite hand-spaced graph positions."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas_scale = 1.0
    graph.node_positions = {
        "npc_a": (120, 140),
        "npc_b": (540, 170),
        "npc_c": (340, 430),
    }
    graph.graph = {
        "nodes": [
            {"tag": "npc_a", "entity_type": "npc", "entity_name": "A", "x": 120, "y": 140},
            {"tag": "npc_b", "entity_type": "npc", "entity_name": "B", "x": 540, "y": 170},
            {"tag": "npc_c", "entity_type": "npc", "entity_name": "C", "x": 340, "y": 430},
        ],
        "links": [
            {"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "A"},
            {"node1_tag": "npc_b", "node2_tag": "npc_c", "text": "B"},
        ],
    }

    ScenarioBoardCharacterGraph._apply_readable_board_layout(graph)

    assert graph.node_positions == {
        "npc_a": (120, 140),
        "npc_b": (540, 170),
        "npc_c": (340, 430),
    }
    assert [(node["x"], node["y"]) for node in graph.graph["nodes"]] == [
        (120, 140),
        (540, 170),
        (340, 430),
    ]
    assert graph.original_positions == graph.node_positions


def test_scenario_board_character_graph_parallel_label_offsets_are_distinct() -> None:
    """Parallel labels should be staggered instead of stacked at the edge midpoint."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas_scale = 1.0
    graph.node_positions = {"npc_a": (200, 200), "npc_b": (600, 200)}
    links = [
        {"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "trust"},
        {"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "fear"},
        {"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "debt"},
    ]

    offsets = ScenarioBoardCharacterGraph._parallel_link_label_offsets(graph, links)
    values = [offsets[ScenarioBoardCharacterGraph._link_canvas_key(graph, link)] for link in links]

    assert len({value["perpendicular"] for value in values}) == 3
    assert all(value["perpendicular"] for value in values)
    assert len({value["along"] for value in values}) == 3


def test_scenario_board_character_graph_link_colors_are_distinct_and_stable() -> None:
    """Board links should get deterministic distinct colours without source mutation."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas_scale = 1.0
    graph.selected_link = None
    graph.node_positions = {
        "npc_a": (100, 100),
        "npc_b": (300, 100),
        "npc_c": (200, 300),
        "npc_d": (420, 300),
    }
    links = [
        {"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "owes"},
        {"node1_tag": "npc_b", "node2_tag": "npc_c", "text": "fears"},
        {"node1_tag": "npc_c", "node2_tag": "npc_d", "text": "trusts"},
        {"node1_tag": "npc_a", "node2_tag": "npc_d", "text": "blackmails"},
    ]
    graph.graph = {
        "nodes": [{"tag": tag} for tag in graph.node_positions],
        "links": links,
    }

    colors = [
        ScenarioBoardCharacterGraph._get_link_style(graph, link)[0]
        for link in links
    ]
    colors_after_redraw = [
        ScenarioBoardCharacterGraph._get_link_style(graph, link)[0]
        for link in links
    ]
    colors_by_text = dict(zip((link["text"] for link in links), colors))

    graph.graph["links"] = list(reversed(links))
    colors_after_reorder = {
        link["text"]: ScenarioBoardCharacterGraph._get_link_style(graph, link)[0]
        for link in links
    }

    graph.selected_link = links[1]
    selected_color, selected_width = ScenarioBoardCharacterGraph._get_link_style(
        graph,
        links[1],
    )
    unselected_color, unselected_width = ScenarioBoardCharacterGraph._get_link_style(
        graph,
        links[0],
    )

    assert len(set(colors)) == len(links)
    assert colors_after_redraw == colors
    assert colors_after_reorder == colors_by_text
    assert selected_color == colors_by_text[links[1]["text"]]
    assert selected_width == 3
    assert unselected_color == colors_by_text[links[0]["text"]]
    assert unselected_width == 2
    assert all("color" not in link for link in links)


def test_scenario_board_character_graph_offsets_non_parallel_labels() -> None:
    """Dense board labels should not all sit on each link's exact midpoint."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas_scale = 1.0
    graph.node_positions = {
        "npc_a": (100, 100),
        "npc_b": (300, 100),
        "npc_c": (200, 300),
    }
    links = [
        {"node1_tag": "npc_a", "node2_tag": "npc_b", "text": "Scene 1"},
        {"node1_tag": "npc_b", "node2_tag": "npc_c", "text": "Scene 2"},
        {"node1_tag": "npc_a", "node2_tag": "npc_c", "text": "Scene 3"},
    ]

    offsets = ScenarioBoardCharacterGraph._parallel_link_label_offsets(graph, links)

    assert all(
        offsets[ScenarioBoardCharacterGraph._link_canvas_key(graph, link)]["perpendicular"]
        for link in links
    )


def test_scenario_board_character_graph_moves_parallel_link_labels_from_current_endpoints() -> None:
    """Parallel labels and backgrounds follow the moved edge, not stale pair IDs."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas = _MovingLinkCanvas()
    graph.canvas_scale = 1.0
    graph.selected_link = None
    graph.link_canvas_ids = {}
    graph.node_positions = {"npc_a": (100, 100), "npc_b": (300, 100)}
    graph.node_bboxes = {
        "npc_a": (90, 90, 110, 110),
        "npc_b": (290, 90, 310, 110),
    }
    link_one = {
        "node1_tag": "npc_a",
        "node2_tag": "npc_b",
        "text": "confiance trahie",
        "arrow_mode": "both",
    }
    link_two = {
        "node1_tag": "npc_a",
        "node2_tag": "npc_b",
        "text": "Scene 5",
        "arrow_mode": "both",
    }
    graph.graph = {
        "nodes": [{"tag": "npc_a"}, {"tag": "npc_b"}],
        "links": [link_one, link_two],
    }

    ScenarioBoardCharacterGraph.draw_all_links(graph, graph.graph["links"])

    initial = {}
    initial_colors = {}
    for link in graph.graph["links"]:
        canvas_ids = graph.link_canvas_ids[ScenarioBoardCharacterGraph._link_canvas_key(graph, link)]
        line_color = graph.canvas.kwargs_by_id[canvas_ids["line"]]["fill"]
        text_color = graph.canvas.kwargs_by_id[canvas_ids["text"]]["fill"]
        arrow_colors = [
            graph.canvas.kwargs_by_id[arrow_id]["fill"]
            for arrow_id in canvas_ids["arrows"]
        ]
        arrow_outlines = [
            graph.canvas.kwargs_by_id[arrow_id]["outline"]
            for arrow_id in canvas_ids["arrows"]
        ]
        initial[link["text"]] = {
            "line": graph.canvas.coords(canvas_ids["line"]),
            "text": graph.canvas.coords(canvas_ids["text"]),
        }
        initial_colors[link["text"]] = line_color
        assert text_color == line_color
        assert arrow_colors == [line_color, line_color]
        assert arrow_outlines == [line_color, line_color]
    assert len(set(initial_colors.values())) == 2

    graph.node_positions["npc_b"] = (300, 200)
    graph.node_bboxes["npc_b"] = (290, 190, 310, 210)

    ScenarioBoardCharacterGraph.update_links_positions_for_node(graph, "npc_b")

    for link in graph.graph["links"]:
        canvas_ids = graph.link_canvas_ids[ScenarioBoardCharacterGraph._link_canvas_key(graph, link)]
        line_coords = graph.canvas.coords(canvas_ids["line"])
        text_coords = graph.canvas.coords(canvas_ids["text"])
        background_coords = graph.canvas.coords(canvas_ids["text_bg"])
        line_color = graph.canvas.kwargs_by_id[canvas_ids["line"]]["fill"]
        text_color = graph.canvas.kwargs_by_id[canvas_ids["text"]]["fill"]
        arrow_colors = [
            graph.canvas.kwargs_by_id[arrow_id]["fill"]
            for arrow_id in canvas_ids["arrows"]
        ]
        arrow_outlines = [
            graph.canvas.kwargs_by_id[arrow_id]["outline"]
            for arrow_id in canvas_ids["arrows"]
        ]
        expected_text = ScenarioBoardCharacterGraph._link_label_position(
            graph,
            *line_coords,
            canvas_ids["label_offset"],
        )

        assert line_coords != initial[link["text"]]["line"]
        assert text_coords != initial[link["text"]]["text"]
        assert text_coords == expected_text
        assert line_color == initial_colors[link["text"]]
        assert text_color == line_color
        assert arrow_colors == [line_color, line_color]
        assert arrow_outlines == [line_color, line_color]
        assert background_coords == (
            expected_text[0] - 25,
            expected_text[1] - 9,
            expected_text[0] + 25,
            expected_text[1] + 9,
        )


def test_scenario_board_character_graph_skips_links_with_missing_endpoints() -> None:
    """Endpoint filtering must remain in the board renderer."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    graph.canvas = _MovingLinkCanvas()
    graph.canvas_scale = 1.0
    graph.selected_link = None
    graph.link_canvas_ids = {}
    graph.node_positions = {"npc_a": (100, 100)}
    graph.node_bboxes = {"npc_a": (90, 90, 110, 110)}

    ScenarioBoardCharacterGraph.draw_one_link(
        graph,
        {
            "node1_tag": "npc_a",
            "node2_tag": "npc_missing",
            "text": "Scene 9",
            "arrow_mode": "both",
        },
    )

    assert graph.link_canvas_ids == {}
    assert graph.canvas.coords_by_id == {}


def test_scenario_board_character_graph_compacts_long_link_labels() -> None:
    """Long merged scene labels are abbreviated for display only."""
    graph = ScenarioBoardCharacterGraph.__new__(ScenarioBoardCharacterGraph)
    source = "Ambush at the East Gate / Vault Negotiation / Final Escape / Epilogue"

    label = ScenarioBoardCharacterGraph._display_link_label(graph, source)

    assert label == "Ambush at the East Gate / Vault Negoti... +2"
    assert source.endswith("Epilogue")


def test_character_graph_editor_edits_selected_parallel_link_by_canvas_tag() -> None:
    """Canvas tags should identify the exact parallel link selected for editing."""
    graph = CharacterGraphEditor.__new__(CharacterGraphEditor)
    link_one = {
        "node1_tag": "npc_a",
        "node2_tag": "npc_b",
        "text": "trust",
        "arrow_mode": "both",
    }
    link_two = {
        "node1_tag": "npc_a",
        "node2_tag": "npc_b",
        "text": "betrayal",
        "arrow_mode": "both",
    }
    graph.graph = {"links": [link_one, link_two]}
    graph.selected_link = CharacterGraphEditor._get_link_by_canvas_tags(
        graph,
        ("link_text", CharacterGraphEditor._link_canvas_item_tag(graph, link_two)),
    )
    persisted = []
    graph._persist_link_to_entities = persisted.append
    graph.draw_graph = lambda: None
    graph._autosave_graph = lambda: None

    CharacterGraphEditor.set_arrow_mode(graph, "start")

    assert graph.selected_link is link_two
    assert link_one["arrow_mode"] == "both"
    assert link_two["arrow_mode"] == "start"
    assert persisted == [link_two]


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


def test_full_width_wrap_accounts_for_customtkinter_display_scaling() -> None:
    """Physical configure widths must be converted before CTk scales them again."""
    from modules.scenarios.gm_table.scenario_board.entity_links import (
        bind_full_width_wrap,
    )

    class _Parent:
        def bind(self, _event_name, callback, *, add):
            assert add == "+"
            self.callback = callback

    class _ScaledLabel:
        def __init__(self):
            self.master = _Parent()
            self.wraplengths = []

        def _reverse_widget_scaling(self, value):
            return value / 1.25

        def configure(self, *, wraplength):
            self.wraplengths.append(wraplength)

    label = _ScaledLabel()
    bind_full_width_wrap(label, padding=14, initial_wraplength=240)
    label.master.callback(SimpleNamespace(width=500))

    # 500 physical pixels are 400 CTk logical pixels at 125% scaling.
    assert label.wraplengths == [240, 386]


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


def test_build_scenario_board_data_extracts_scene_entities_blob() -> None:
    """Scene entity blobs should create clickable Scenario Board links."""
    data = build_scenario_board_data(
        {
            "Title": "Safehouse Job",
            "Scenes": [
                {
                    "Title": "Escape",
                    "Text": "Get out before the raid closes in.",
                    "Entities": {
                        "NPCs": ["Rika Vale"],
                        "Places": ["Rainmarket"],
                        "Villains": ["Marshal Vey"],
                    },
                }
            ],
        }
    )

    scene = data.scenes[0]
    assert scene.npcs == ("Rika Vale",)
    assert data.linked_entities["NPCs"] == ("Rika Vale",)


def test_build_scenario_board_data_extracts_untyped_scene_actor_names() -> None:
    """Actor blobs without explicit entity types should still create NPC links."""
    data = build_scenario_board_data(
        {
            "Title": "Safehouse Job",
            "Scenes": [
                {
                    "Title": "Negotiation",
                    "Text": "Talk the broker into opening the vault.",
                    "Actors": [{"Name": "Rika Vale"}],
                    "Entities": [{"Name": "Rainmarket"}],
                }
            ],
        }
    )

    scene = data.scenes[0]
    assert scene.npcs == ("Rika Vale",)
    assert data.linked_entities["NPCs"] == ("Rika Vale",)


def test_build_scenario_board_data_uses_involved_npcs_section_for_links() -> None:
    """NPC names written in scene body sections should become board links."""
    data = build_scenario_board_data(
        {
            "Title": "Industrial Infiltration",
            "Scenes": [
                (
                    "Control Room\n"
                    "The crew enters through service corridors.\n"
                    "Involved NPCs: Director Vale, Security Guard\n"
                    "Important locations: Control Room"
                )
            ],
        }
    )

    scene = data.scenes[0]
    assert scene.npcs == ("Director Vale", "Security Guard")
    assert data.linked_entities["NPCs"] == ("Director Vale", "Security Guard")


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
