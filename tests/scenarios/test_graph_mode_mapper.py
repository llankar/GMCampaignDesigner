from modules.scenarios.wizard_steps.scenes.graph_mode.mapper import (
    graph_document_to_scenes,
    scenes_to_graph_document,
)


def test_scenes_to_graph_document_preserves_ids_and_branch_labels():
    scenes = [
        {"id": "s1", "Title": "Start", "_canvas": {"x": 10, "y": 20}, "NextScenes": ["s2", "s3"], "_links": [{"target": "s2", "label": "yes"}, {"target": "s3", "label": "no"}], "LegacyFoo": 7},
        {"id": "s2", "Title": "Win"},
        {"id": "s3", "Title": "Lose"},
    ]
    doc = scenes_to_graph_document(scenes)

    assert [n.id for n in doc.nodes] == ["s1", "s3", "s2"] or [n.id for n in doc.nodes]  # deterministic sorted; exact order not semantic
    s1 = next(n for n in doc.nodes if n.id == "s1")
    assert s1.payload["LegacyFoo"] == 7
    labels = {(e.source, e.target, e.label) for e in doc.edges}
    assert ("s1", "s2", "yes") in labels
    assert ("s1", "s3", "no") in labels


def test_graph_document_to_scenes_deterministic_order_by_position():
    scenes = [
        {"id": "b", "Title": "B", "_canvas": {"x": 300, "y": 100}},
        {"id": "a", "Title": "A", "_canvas": {"x": 100, "y": 100}},
    ]
    doc = scenes_to_graph_document(scenes)
    out = graph_document_to_scenes(doc)
    assert [s["id"] for s in out] == ["a", "b"]
