from modules.scenarios.wizard_steps.scenes.canvas_scene_planner import CanvasScenePlanner


class _FakeCanvas:
    def __init__(self):
        self.calls = []

    def set_scenes(self, scenes, selected_index):
        self.calls.append((scenes, selected_index))


def test_apply_inline_scene_update_migrates_incoming_links_on_title_rename():
    planner = CanvasScenePlanner.__new__(CanvasScenePlanner)
    planner.scenes = [
        {
            "Title": "Intro",
            "Summary": "",
            "SceneType": "",
            "LinkData": [{"target": "Target", "text": "Go to target"}],
            "NextScenes": ["Target"],
        },
        {
            "Title": "Target",
            "Summary": "",
            "SceneType": "",
            "LinkData": [],
            "NextScenes": [],
        },
    ]
    planner.selected_index = 1
    planner.canvas = _FakeCanvas()
    planner._inline_editor = None
    planner._close_inline_scene_editor = lambda: None

    planner._apply_inline_scene_update(
        1,
        {
            "Title": "Target Renamed",
            "Summary": "Updated summary",
            "SceneType": "Outcome",
            "_structured_prefilled": False,
        },
    )

    source_scene = planner.scenes[0]
    renamed_scene = planner.scenes[1]

    assert renamed_scene["Title"] == "Target Renamed"
    assert source_scene["LinkData"] == [{"target": "Target Renamed", "text": "Go to target"}]
    assert source_scene["NextScenes"] == ["Target Renamed"]
    assert all(link["target"] != "Target" for link in source_scene["LinkData"])
    assert "Target" not in source_scene["NextScenes"]
    assert planner.canvas.calls, "Canvas should refresh after link migration"
