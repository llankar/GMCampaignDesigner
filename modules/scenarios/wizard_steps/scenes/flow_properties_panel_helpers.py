"""Helpers for visual flow properties panel editing."""

from __future__ import annotations

SCENE_ENTITY_FIELDS = ("NPCs", "Creatures", "Places", "Clues", "Bases", "Maps")
SCENE_STRUCTURED_FIELDS = ("SceneBeats", "SceneClues", "SceneChallenges", "SceneTwists", "SceneRewards")
NODE_KIND_VALUES = ["scene", "objective", "side_objective", "interaction", "condition", "action", "note", "start", "end"]
LINK_KIND_VALUES = ["scene_link", "yes", "no", "success", "failure"]


def string_list_from_multiline(value: str) -> list[str]:
    """Convert textarea text into a cleaned list of string lines."""
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def multiline_from_value(value) -> str:
    """Render scalar/list values into multi-line text for editing."""
    if isinstance(value, (list, tuple, set)):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "")
