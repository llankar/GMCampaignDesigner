from modules.scenarios.wizard_steps.scenes.graph_mode.validation import validate_scenes


def _scene(node_id: str, node_type: str):
    return {"id": node_id, "type": node_type, "title": node_id}


def test_requires_exactly_one_start():
    scenes = [_scene("a", "START"), _scene("b", "START"), _scene("end", "END_SUCCESS")]
    issues = validate_scenes(scenes, [])
    assert any(i.code == "start_count" and i.blocking for i in issues)


def test_reachable_end_is_required_and_orphan_detected():
    scenes = [_scene("start", "START"), _scene("mid", "SCENE"), _scene("end", "END_SUCCESS")]
    edges = [{"id": "e1", "source": "start", "target": "mid"}]
    issues = validate_scenes(scenes, edges)
    assert any(i.code == "missing_reachable_end" for i in issues)
    assert any(i.code == "orphan_node" and i.node_id == "end" for i in issues)


def test_choice_and_condition_rules():
    scenes = [_scene("start", "START"), _scene("choice", "CHOICE"), _scene("cond", "CONDITION"), _scene("end", "END_FAIL")]
    edges = [
        {"id": "e1", "source": "start", "target": "choice"},
        {"id": "e2", "source": "choice", "target": "cond"},
        {"id": "e3", "source": "cond", "target": "end", "condition_value": "yes"},
    ]
    issues = validate_scenes(scenes, edges)
    assert any(i.code == "choice_outgoing" for i in issues)
    assert any(i.code == "condition_exits" for i in issues)
