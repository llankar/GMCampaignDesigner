from __future__ import annotations

COMPONENT_GROUPS = [
    {
        "name": "Objectives",
        "items": [
            {"kind": "objective", "label": "Objective", "icon": "🎯", "color": "#34d399"},
            {"kind": "side_objective", "label": "Side Objective", "icon": "🧭", "color": "#60a5fa"},
        ],
    },
    {
        "name": "Dialogue/Interaction",
        "items": [
            {"kind": "interaction", "label": "Interaction", "icon": "💬", "color": "#f59e0b"},
            {"kind": "condition", "label": "Condition", "icon": "❓", "color": "#c084fc"},
        ],
    },
    {
        "name": "Actions",
        "items": [
            {"kind": "action", "label": "Action", "icon": "⚡", "color": "#f87171"},
        ],
    },
    {
        "name": "Other",
        "items": [
            {"kind": "scene", "label": "Scene", "icon": "🎬", "color": "#60a5fa"},
            {"kind": "note", "label": "Note", "icon": "📝", "color": "#a3a3a3"},
        ],
    },
]
