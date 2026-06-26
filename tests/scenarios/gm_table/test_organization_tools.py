from modules.scenarios.gm_table.organization.layout_tools import (
    align_geometries,
    distribute_geometries,
    eligible_panel_records,
)
from modules.scenarios.gm_table.organization.search_index import (
    build_panel_search_index,
    filter_panel_search_index,
)
from modules.scenarios.gm_table.workspace import PanelDefinition


def test_align_geometries_left_and_bottom():
    geometries = [
        {"x": 30, "y": 20, "width": 100, "height": 50},
        {"x": 10, "y": 80, "width": 80, "height": 40},
    ]
    assert [g["x"] for g in align_geometries(geometries, "left")] == [10, 10]
    assert [g["y"] for g in align_geometries(geometries, "bottom")] == [70, 80]


def test_distribute_geometries_horizontal_evenly_preserves_input_order():
    geometries = [
        {"x": 100, "y": 0, "width": 10, "height": 10},
        {"x": 0, "y": 0, "width": 10, "height": 10},
        {"x": 40, "y": 0, "width": 10, "height": 10},
    ]
    distributed = distribute_geometries(geometries, "horizontal")
    assert [g["x"] for g in distributed] == [100, 0, 50]
    assert sorted(g["x"] for g in distributed) == [0, 50, 100]


def test_eligible_panel_records_skip_locked_and_minimized():
    records = [
        {"panel_id": "a", "locked": False, "layout_mode": "floating"},
        {"panel_id": "b", "locked": True, "layout_mode": "floating"},
        {"panel_id": "c", "locked": False, "layout_mode": "minimized"},
    ]
    assert [r["panel_id"] for r in eligible_panel_records(records)] == ["a"]


def test_search_index_matches_title_kind_and_state_flags():
    records = [
        {
            "definition": PanelDefinition("p1", "sticky_note", "Secret Clue", {"text": "dragon key"}),
            "layout_mode": "minimized",
            "locked": True,
        },
        {
            "definition": PanelDefinition("p2", "map_tool", "Town Map", {"map_name": "Harbor"}),
            "layout_mode": "floating",
        },
    ]
    index = build_panel_search_index(records)
    assert filter_panel_search_index(index, "dragon sticky")[0].panel_id == "p1"
    assert index[0].locked is True
    assert index[0].minimized is True

from modules.scenarios.gm_table.organization.alignment import same_size_geometries, snap_geometries_to_grid
from modules.scenarios.gm_table.organization.sticky_notes import (
    cluster_group_geometries,
    group_sticky_notes,
    normalize_tags,
    sticky_note_state,
)


def test_same_size_and_snap_geometries():
    geometries = [
        {"x": 13, "y": 35, "width": 100, "height": 40},
        {"x": 51, "y": 47, "width": 80, "height": 90},
    ]
    assert [g["width"] for g in same_size_geometries(geometries, "width")] == [100, 100]
    assert [g["height"] for g in same_size_geometries(geometries, "height")] == [90, 90]
    assert [(g["x"], g["y"]) for g in snap_geometries_to_grid(geometries, 24)] == [(24, 24), (48, 48)]


def test_sticky_note_state_serializes_rich_fields_and_legacy_text():
    state = sticky_note_state(
        title="Plan",
        body="Storm the keep",
        color="Pink",
        tags="quest, urgent #Quest",
        vote_marker="3/5",
        pinned=True,
    )
    assert state["title"] == "Plan"
    assert state["body"] == "Storm the keep"
    assert state["text"] == "Storm the keep"
    assert state["color"] == "Pink"
    assert state["tags"] == ["quest", "urgent"]
    assert state["vote_marker"] == "3/5"
    assert state["pinned"] is True


def test_sticky_note_grouping_by_tag_and_color_and_cluster_geometry():
    records = [
        {"panel_id": "a", "definition": PanelDefinition("a", "sticky_note", "A", {"tags": ["clue", "npc"], "color": "Yellow"}), "geometry": {"x": 9, "y": 9, "width": 120, "height": 80}},
        {"panel_id": "b", "definition": PanelDefinition("b", "sticky_note", "B", {"tags": ["clue"], "color": "Blue"}), "geometry": {"x": 9, "y": 9, "width": 120, "height": 80}},
    ]
    by_tag = group_sticky_notes(records, "tag")
    assert [record["panel_id"] for record in by_tag["clue"]] == ["a", "b"]
    assert list(group_sticky_notes(records, "color")) == ["Yellow", "Blue"]
    placements = cluster_group_geometries({"clue": records}, start_x=10, start_y=20, gap=5, columns=2)
    assert placements["a"]["x"] == 10
    assert placements["b"]["x"] == 135
    assert placements["a"]["y"] == placements["b"]["y"] == 20


def test_sticky_note_cluster_spacing_uses_actual_widths():
    records = [
        {"panel_id": "wide", "definition": PanelDefinition("wide", "sticky_note", "Wide", {"tags": ["a"]}), "geometry": {"x": 0, "y": 0, "width": 640, "height": 80}},
        {"panel_id": "next", "definition": PanelDefinition("next", "sticky_note", "Next", {"tags": ["b"]}), "geometry": {"x": 0, "y": 0, "width": 120, "height": 80}},
    ]
    placements = cluster_group_geometries({"a": [records[0]], "b": [records[1]]}, start_x=10, group_gap=40)
    assert placements["next"]["x"] >= placements["wide"]["x"] + placements["wide"]["width"] + 40


def test_sticky_note_cluster_columns_use_widest_panel_in_column():
    records = [
        {"panel_id": "wide", "definition": PanelDefinition("wide", "sticky_note", "Wide", {"tags": ["a"]}), "geometry": {"x": 0, "y": 0, "width": 640, "height": 80}},
        {"panel_id": "next", "definition": PanelDefinition("next", "sticky_note", "Next", {"tags": ["a"]}), "geometry": {"x": 0, "y": 0, "width": 120, "height": 80}},
    ]
    placements = cluster_group_geometries({"a": records}, start_x=10, gap=40, columns=2)
    assert placements["next"]["x"] >= placements["wide"]["x"] + placements["wide"]["width"] + 40


def test_sticky_note_state_defaults_blank_color_to_yellow():
    assert sticky_note_state(color="  ")["color"] == "Yellow"


def test_search_index_matches_sticky_title_body_tags_and_nested_state():
    records = [
        {
            "definition": PanelDefinition("p1", "sticky_note", "Sticky", {"title": "Dragon Vote", "body": "Key under altar", "tags": ["clue", "boss"], "meta": {"count": 4}}),
            "layout_mode": "floating",
        },
    ]
    index = build_panel_search_index(records)
    assert filter_panel_search_index(index, "altar boss")[0].panel_id == "p1"
    assert filter_panel_search_index(index, "count 4")[0].panel_id == "p1"
