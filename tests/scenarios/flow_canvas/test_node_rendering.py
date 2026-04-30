from modules.scenarios.wizard_steps.scenes.flow_canvas.node_rendering import resolve_node_visual


def test_resolve_node_visual_snapshot_by_kind():
    snapshot = {
        "scene": ("card_scene", "#1f2937", "#60a5fa", "●"),
        "objective": ("card_objective", "#1f3a2e", "#34d399", "◆"),
        "side_objective": ("card_side_objective", "#1b3448", "#38bdf8", "◇"),
        "interaction": ("card_interaction", "#31253f", "#a78bfa", "◎"),
        "condition": ("diamond", "#3b2f1f", "#f59e0b", "?"),
        "action": ("card_action", "#2f1f3b", "#c084fc", "▶"),
        "note": ("note", "#2d2d2d", "#a3a3a3", "■"),
    }

    for kind, expected in snapshot.items():
        visual = resolve_node_visual(kind)
        assert (visual["shape"], visual["body_fill"], visual["body_outline"], visual["symbol"]) == expected


def test_resolve_node_visual_selection_and_fallback_snapshot():
    selected = resolve_node_visual("condition", selected=True)
    fallback = resolve_node_visual("unknown_kind")

    assert (selected["body_outline"], selected["body_width"]) == ("#e2e8f0", 3)
    assert (fallback["shape"], fallback["body_fill"], fallback["symbol"]) == ("card_scene", "#1f2937", "●")
