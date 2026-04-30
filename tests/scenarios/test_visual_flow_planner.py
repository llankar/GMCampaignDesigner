from modules.scenarios.wizard_steps.scenes.flow_canvas.model import FlowCanvasModel
from modules.scenarios.wizard_steps.scenes.visual_flow_planner import (
    build_visual_flow_from_scenes,
    export_visual_flow_to_scenes,
    normalise_flow_node_id,
)


def test_builds_nodes_from_canonical_scenes_and_linkdata_priority():
    scenes = [
        {
            "Title": "Start",
            "Summary": "A",
            "SceneType": "Investigation",
            "LinkData": [{"target": "Middle", "text": "Go"}],
            "NextScenes": ["Fallback"],
            "_canvas": {"x": 11, "y": 22},
            "SceneClues": ["sigil"],
        },
        {"Title": "Middle", "Summary": "B", "SceneType": "Combat", "LinkData": [], "NextScenes": []},
    ]

    payload = build_visual_flow_from_scenes(scenes)

    assert len(payload["nodes"]) == 2
    assert payload["nodes"][0]["id"] == "start"
    assert payload["nodes"][0]["x"] == 11
    assert payload["nodes"][0]["y"] == 22
    assert payload["nodes"][0]["scene_fields"]["SceneType"] == "Investigation"
    assert payload["nodes"][0]["scene_fields"]["structured"]["SceneClues"] == ["sigil"]
    assert len(payload["links"]) == 1
    assert payload["links"][0]["source"] == "start"
    assert payload["links"][0]["target"] == "middle"


def test_reuses_existing_visual_nodes_and_preserves_unknown_keys():
    scenes = [{"Title": "Opening", "Summary": "Hello", "SceneType": ""}]
    existing = {
        "nodes": [
            {
                "id": "keep-me",
                "title": "Opening",
                "scene_index": 99,
                "x": 300,
                "y": 400,
                "kind": "custom",
                "mystery": {"ok": True},
            }
        ],
        "links": [],
    }

    payload = build_visual_flow_from_scenes(scenes, existing_visual_payload=existing)

    assert payload["nodes"][0]["id"] == "keep-me"
    assert payload["nodes"][0]["kind"] == "custom"
    assert payload["nodes"][0]["_extra_fields"]["mystery"] == {"ok": True}


def test_visual_flow_loads_existing_scenes_without_visual_payload():
    scenes = [
        {"Title": "Arrival", "Summary": "Start", "SceneType": "Setup", "NextScenes": ["Climax"]},
        {"Title": "Climax", "Summary": "End", "SceneType": "Finale", "NextScenes": []},
    ]

    payload = build_visual_flow_from_scenes(scenes)

    assert [node["title"] for node in payload["nodes"]] == ["Arrival", "Climax"]
    assert all(isinstance(node["x"], int) and isinstance(node["y"], int) for node in payload["nodes"])
    assert payload["links"] == [{"id": "arrival-climax", "source": "arrival", "target": "climax", "label": "", "kind": "scene_link", "_extra_fields": {}}]


def test_visual_flow_round_trip_preserves_scene_fields():
    scenes = [
        {
            "Title": "Dockside",
            "Summary": "Meet contact",
            "SceneType": "Interaction",
            "SceneClues": ["Blue wax seal"],
            "NPCs": ["Vera"],
            "NextScenes": ["Ambush"],
        },
        {
            "Title": "Ambush",
            "Summary": "Fight breaks out",
            "SceneType": "Action",
            "Creatures": ["Cultist"],
            "NextScenes": [],
        },
    ]

    exported = export_visual_flow_to_scenes(build_visual_flow_from_scenes(scenes), existing_scenes=scenes)

    by_title = {scene["Title"]: scene for scene in exported}
    assert by_title["Dockside"]["SceneClues"] == ["Blue wax seal"]
    assert by_title["Dockside"]["NPCs"] == ["Vera"]
    assert by_title["Ambush"]["Creatures"] == ["Cultist"]
    assert by_title["Dockside"]["NextScenes"] == ["Ambush"]


def test_visual_flow_exports_linkdata_and_nextscenes():
    flow_payload = {
        "version": 1,
        "nodes": [
            {"id": "a", "scene_index": 0, "title": "Start", "summary": "", "kind": "scene", "x": 0, "y": 0},
            {"id": "b", "scene_index": 1, "title": "Market", "summary": "", "kind": "scene", "x": 0, "y": 0},
        ],
        "links": [{"id": "a-b", "source": "a", "target": "b", "label": "Follow", "kind": "scene_link"}],
    }

    scenes = export_visual_flow_to_scenes(flow_payload)
    by_title = {scene["Title"]: scene for scene in scenes}
    assert by_title["Start"]["LinkData"] == [{"target": "Market", "text": "Follow"}]
    assert by_title["Start"]["NextScenes"] == ["Market"]


def test_visual_flow_delete_node_removes_links():
    model = FlowCanvasModel(
        {
            "version": 1,
            "nodes": [{"id": "a"}, {"id": "b"}],
            "links": [{"id": "a-b", "source": "a", "target": "b"}],
        }
    )

    assert model.remove_node("a") is True
    assert model.payload["nodes"] == [{"id": "b"}]
    assert model.payload["links"] == []


def test_visual_flow_unique_ids():
    used = {"scene", "scene-2"}
    assert normalise_flow_node_id("Scene", used) == "scene-3"
