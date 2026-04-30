"""Shared constants and root-shape validation helpers for scenario payloads."""
from __future__ import annotations

import copy
from typing import Any

PRESERVED_SCENARIO_ROOT_KEYS: tuple[str, ...] = (
    "Title",
    "Summary",
    "Secrets",
    "Secret",
    "Scenes",
    "_SceneLayout",
    "NPCs",
    "Creatures",
    "Places",
    "Clues",
    "Bases",
    "Maps",
    "Factions",
    "Objects",
    "Books",
    "Villains",
    "Events",
    "SceneBeats",
    "SceneClues",
    "SceneChallenges",
    "SceneTwists",
    "SceneRewards",
    "LinkData",
    "NextScenes",
    "_canvas",
    "_extra_fields",
)

ADDITIVE_SCENARIO_METADATA_KEYS: tuple[str, ...] = ("_ScenarioVisualFlow",)

SCENARIO_ROOT_KNOWN_FIELDS: frozenset[str] = frozenset(
    PRESERVED_SCENARIO_ROOT_KEYS
    + ADDITIVE_SCENARIO_METADATA_KEYS
    + (
        "Text",
        "NPCs",
        "Creatures",
        "Clues",
        "Bases",
        "Places",
        "Maps",
        "Factions",
        "Objects",
        "Books",
        "Villains",
        "Events",
    )
)


def ensure_required_scenario_root_keys(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure required scenario root keys exist without renaming/removing existing keys."""
    if not isinstance(state, dict):
        return state

    defaults = {
        "Title": "",
        "Summary": "",
        "Secrets": "",
        "Secret": "",
        "Scenes": [],
        "_SceneLayout": [],
        "NPCs": [],
        "Creatures": [],
        "Places": [],
        "Clues": [],
        "Bases": [],
        "Maps": [],
        "Factions": [],
        "Objects": [],
        "Books": [],
        "Villains": [],
        "Events": [],
        "SceneBeats": [],
        "SceneClues": [],
        "SceneChallenges": [],
        "SceneTwists": [],
        "SceneRewards": [],
        "LinkData": [],
        "NextScenes": [],
        "_canvas": {},
        "_extra_fields": {},
    }
    for key, default_value in defaults.items():
        state.setdefault(key, copy.deepcopy(default_value))

    state.setdefault("_ScenarioVisualFlow", {})
    return state
