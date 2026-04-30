from __future__ import annotations

DEFAULT_NODE_KIND = "scene"

_NODE_BASE_STYLE = {
    "title_color": "#f8fafc",
    "title_accent": "#94a3b8",
    "body_fill": "#0f172a",
    "body_outline": "#334155",
    "body_width": 2,
    "handle_fill": "#38bdf8",
    "handle_outline": "",
    "selected_outline": "#e2e8f0",
    "selected_width": 3,
    "shape": "card",
    "symbol": "●",
}

NODE_STYLES = {
    "scene": {**_NODE_BASE_STYLE, "body_fill": "#1f2937", "body_outline": "#60a5fa", "symbol": "●", "shape": "card_scene"},
    "objective": {**_NODE_BASE_STYLE, "body_fill": "#1f3a2e", "body_outline": "#34d399", "symbol": "◆", "shape": "card_objective"},
    "side_objective": {**_NODE_BASE_STYLE, "body_fill": "#1b3448", "body_outline": "#38bdf8", "symbol": "◇", "shape": "card_side_objective"},
    "interaction": {**_NODE_BASE_STYLE, "body_fill": "#31253f", "body_outline": "#a78bfa", "symbol": "◎", "shape": "card_interaction"},
    "condition": {**_NODE_BASE_STYLE, "body_fill": "#3b2f1f", "body_outline": "#f59e0b", "symbol": "?", "shape": "diamond"},
    "action": {**_NODE_BASE_STYLE, "body_fill": "#2f1f3b", "body_outline": "#c084fc", "symbol": "▶", "shape": "card_action"},
    "note": {**_NODE_BASE_STYLE, "body_fill": "#2d2d2d", "body_outline": "#a3a3a3", "symbol": "■", "shape": "note"},
}


def resolve_node_visual(kind: str, selected: bool = False) -> dict:
    style = dict(NODE_STYLES.get(str(kind or "").strip(), NODE_STYLES[DEFAULT_NODE_KIND]))
    style["kind"] = kind if kind in NODE_STYLES else DEFAULT_NODE_KIND
    if selected:
        style["body_outline"] = style["selected_outline"]
        style["body_width"] = style["selected_width"]
    return style
