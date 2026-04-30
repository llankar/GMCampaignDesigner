from modules.scenarios.wizard_steps.scenes.flow_canvas.model import FlowCanvasModel
from modules.scenarios.wizard_steps.scenes.visual_flow_planner import (
    VisualFlowPlanner,
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


def test_visual_flow_round_trip_preserves_node_kinds_via_extra_metadata():
    flow_payload = {
        "version": 1,
        "nodes": [
            {"id": "n1", "scene_index": 0, "title": "Objective", "summary": "", "kind": "objective", "x": 0, "y": 0},
            {"id": "n2", "scene_index": 1, "title": "Condition", "summary": "", "kind": "condition", "x": 0, "y": 0},
            {"id": "n3", "scene_index": 2, "title": "Fallback", "summary": "", "kind": "scene", "x": 0, "y": 0},
        ],
        "links": [],
    }

    scenes = export_visual_flow_to_scenes(flow_payload)
    rebuilt = build_visual_flow_from_scenes(scenes)
    by_title = {node["title"]: node for node in rebuilt["nodes"]}
    assert by_title["Objective"]["kind"] == "objective"
    assert by_title["Condition"]["kind"] == "condition"
    assert by_title["Fallback"]["kind"] == "scene"


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


class _FakeCanvas:
    def __init__(self, payload):
        self.model = FlowCanvasModel(payload)
        self.render_calls = 0
        self.created = 0
        self.selected = None

    def render(self):
        self.render_calls += 1

    def create_node_at_viewport_center(self, kind):
        self.created += 1
        node = {"id": f"new-{self.created}", "title": f"{kind} node", "kind": kind, "scene_index": len(self.model.payload.get("nodes") or []), "x": 10, "y": 20}
        self.model.payload.setdefault("nodes", []).append(node)
        return node

    def select_node(self, node_id, emit=False):
        self.selected = (node_id, emit)


class _FakeHierarchy:
    def __init__(self):
        self.calls = 0

    def render(self, *_args, **_kwargs):
        self.calls += 1

    def select_node(self, *_args, **_kwargs):
        return None


def _build_headless_planner(payload):
    planner = VisualFlowPlanner.__new__(VisualFlowPlanner)
    planner.canvas = _FakeCanvas(payload)
    planner.hierarchy = _FakeHierarchy()
    planner.properties = type("P", (), {"bind_item": lambda *args, **kwargs: None})()
    planner._scenario_title = "Test"
    planner._dirty = False
    planner._clipboard_node = None
    return planner


def test_planner_context_commands_delete_reorder_and_copy_paste():
    planner = _build_headless_planner(
        {
            "version": 1,
            "nodes": [
                {"id": "a", "title": "A", "kind": "scene", "scene_index": 0, "x": 0, "y": 0},
                {"id": "b", "title": "B", "kind": "scene", "scene_index": 1, "x": 0, "y": 0},
            ],
            "links": [{"id": "a-b", "source": "a", "target": "b", "label": "", "kind": "scene_link"}],
        }
    )
    planner._handle_hierarchy_command("move_down", {"node_id": "a"})
    nodes = planner.canvas.model.payload["nodes"]
    assert [node["id"] for node in nodes] == ["b", "a"]
    assert [node["scene_index"] for node in nodes] == [0, 1]

    planner._handle_hierarchy_command("copy", {"node_id": "a"})
    planner._handle_hierarchy_command("paste", {"node_id": None})
    ids = [node["id"] for node in planner.canvas.model.payload["nodes"]]
    assert len(ids) == 3
    assert len(set(ids)) == 3

    planner._handle_hierarchy_command("cut", {"node_id": "b"})
    assert planner.canvas.model.get_node("b") is None


def test_planner_add_and_paste_anchor_generate_valid_links():
    planner = _build_headless_planner({"version": 1, "nodes": [{"id": "root", "title": "Root", "kind": "scene", "scene_index": 0, "x": 0, "y": 0}], "links": []})
    planner._handle_hierarchy_command("add", {"node_id": "root", "node_type": "objective"})
    added = [node for node in planner.canvas.model.payload["nodes"] if node["id"] != "root"][0]
    assert added["kind"] == "objective"
    assert any(link["source"] == "root" and link["target"] == added["id"] for link in planner.canvas.model.payload["links"])

    planner._handle_hierarchy_command("copy", {"node_id": added["id"]})
    planner._handle_hierarchy_command("paste", {"node_id": "root"})
    latest_id = planner.canvas.model.payload["nodes"][-1]["id"]
    assert any(link["source"] == "root" and link["target"] == latest_id for link in planner.canvas.model.payload["links"])
