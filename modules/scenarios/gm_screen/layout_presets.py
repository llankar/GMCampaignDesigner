"""Preset rules for GM Screen virtual desk tab placement."""

from __future__ import annotations

from typing import Any

DEFAULT_LAYOUT_PRESETS: dict[str, dict[str, Any]] = {
    "Narration": {
        "description": "Focus narration tools at center, references on side, trackers below.",
        "rules": {
            "kinds": {
                "entity": "center",
                "note": "center",
                "world_map": "right",
                "map_tool": "right",
                "scene_flow": "right",
                "campaign_dashboard": "right",
                "plot_twists": "bottom",
                "random_tables": "bottom",
                "loot_generator": "bottom",
            },
            "exact_name": {
                "session timer": "bottom",
            },
            "name_contains": {
                "timer": "bottom",
                "twist": "bottom",
                "random": "bottom",
                "map": "right",
            },
        },
    },
    "Exploration": {
        "description": "Keep map and location context in focus.",
        "rules": {
            "kinds": {
                "world_map": "center",
                "map_tool": "center",
                "scene_flow": "right",
                "entity": "right",
                "note": "right",
                "random_tables": "bottom",
                "loot_generator": "bottom",
            },
            "exact_name": {
                "world map": "center",
                "session timer": "bottom",
            },
            "name_contains": {
                "world map": "center",
                "map": "center",
                "timer": "bottom",
                "loot": "bottom",
            },
        },
    },
    "Combat": {
        "description": "Keep initiative aids and tactical references visible.",
        "rules": {
            "kinds": {
                "world_map": "center",
                "map_tool": "center",
                "random_tables": "right",
                "loot_generator": "right",
                "entity": "right",
                "note": "bottom",
                "scene_flow": "bottom",
            },
            "exact_name": {
                "session timer": "bottom",
                "world map": "center",
            },
            "name_contains": {
                "combat": "center",
                "initiative": "center",
                "timer": "bottom",
                "npc": "right",
                "creature": "right",
            },
        },
    },
    "Prep": {
        "description": "Prioritize planning material and references.",
        "rules": {
            "kinds": {
                "campaign_dashboard": "center",
                "scene_flow": "center",
                "note": "center",
                "entity": "right",
                "world_map": "right",
                "map_tool": "right",
                "random_tables": "bottom",
                "whiteboard": "bottom",
            },
            "exact_name": {
                "session timer": "bottom",
            },
            "name_contains": {
                "world map": "right",
                "map": "right",
                "timer": "bottom",
                "note": "center",
            },
        },
    },
}


def _normalized_ruleset(preset: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    """Return a normalized rules dictionary from persisted preset data."""
    raw_rules = (preset or {}).get("rules")
    if not isinstance(raw_rules, dict):
        return {"exact_name": {}, "name_contains": {}, "kinds": {}}

    output: dict[str, dict[str, str]] = {"exact_name": {}, "name_contains": {}, "kinds": {}}
    for rule_key in output:
        entries = raw_rules.get(rule_key)
        if not isinstance(entries, dict):
            continue
        for source, zone in entries.items():
            source_key = str(source or "").strip().lower()
            zone_value = str(zone or "").strip().lower()
            if source_key and zone_value:
                output[rule_key][source_key] = zone_value
    return output


def resolve_zone_for_tab(tab_name: str, tab_meta: dict[str, Any] | None, preset: dict[str, Any]) -> str | None:
    """Resolve a target zone for a tab from preset rules."""
    rules = _normalized_ruleset(preset)
    normalized_name = str(tab_name or "").strip().lower()
    meta = tab_meta if isinstance(tab_meta, dict) else {}
    kind = str(meta.get("kind") or "").strip().lower()

    if normalized_name in rules["exact_name"]:
        return rules["exact_name"][normalized_name]

    for needle, zone in rules["name_contains"].items():
        if needle and needle in normalized_name:
            return zone

    if kind in rules["kinds"]:
        return rules["kinds"][kind]

    return None


def build_snapshot_preset(tab_definitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a preset from current tabs using exact title+kind matches."""
    exact_name: dict[str, str] = {}
    kinds: dict[str, str] = {}

    for entry in tab_definitions:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip().lower()
        kind = str(entry.get("kind") or "").strip().lower()
        zone = str(entry.get("ui_zone") or "").strip().lower()
        if not zone:
            continue
        if title:
            exact_name[title] = zone
        if kind and kind not in kinds:
            kinds[kind] = zone

    return {
        "description": "Captured from current GM screen layout.",
        "rules": {
            "exact_name": exact_name,
            "name_contains": {},
            "kinds": kinds,
        },
    }
