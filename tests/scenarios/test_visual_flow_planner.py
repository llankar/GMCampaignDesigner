from modules.scenarios.wizard_steps.scenes.visual_flow_planner import build_visual_flow_from_scenes


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
