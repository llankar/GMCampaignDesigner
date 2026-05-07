"""Reference and hierarchy rules for campaign entities."""

from __future__ import annotations

from typing import Mapping

# Explicit mapping: field path -> expected referenced entity type.
#
# Persisted campaign/scenario template fields are accepted for direct validator
# callers. UI validation normalizes linked-list fields into canonical ``*_refs``
# aliases before traversal so reference records use stable validator fields.
FIELD_EXPECTED_TYPES: Mapping[str, str] = {
    # Campaign fields from modules/campaigns/campaigns_template.json.
    "campaign.Arcs": "arc",
    "campaign.LinkedScenarios": "scenario",
    # Scenario fields from modules/scenarios/scenarios_template.json.
    "scenario.Bases": "base",
    "scenario.Places": "location",
    "scenario.Maps": "map",
    "scenario.NPCs": "npc",
    "scenario.PCs": "pc",
    "scenario.Villains": "villain",
    "scenario.Events": "event",
    "scenario.Creatures": "creature",
    "scenario.Factions": "faction",
    "scenario.Objects": "object",
    "scenario.Books": "book",
    # Canonical validator aliases populated by field normalization.
    "campaign.arc_refs": "arc",
    "campaign.scenario_refs": "scenario",
    "arc.scenario_refs": "scenario",
    "arc.location_refs": "location",
    "scenario.base_refs": "base",
    "scenario.location_refs": "location",
    "scenario.map_refs": "map",
    "scenario.encounter_refs": "encounter",
    "scenario.npc_refs": "npc",
    "scenario.pc_refs": "pc",
    "scenario.villain_refs": "villain",
    "scenario.event_refs": "event",
    "scenario.creature_refs": "creature",
    "scenario.faction_refs": "faction",
    "scenario.object_refs": "object",
    "scenario.book_refs": "book",
}

# Parent type -> allowed child types
ALLOWED_HIERARCHY_CHILDREN: Mapping[str, set[str]] = {
    "campaign": {"arc"},
    "arc": {"scenario", "location"},
    "scenario": {
        "base",
        "book",
        "creature",
        "encounter",
        "event",
        "faction",
        "location",
        "map",
        "npc",
        "object",
        "pc",
        "villain",
    },
}


def format_hierarchy_context(path: list[str] | tuple[str, ...]) -> str:
    """Formats hierarchy path for UI display (e.g. campaign > arc > scenario)."""

    return " > ".join(path)


def format_parent_child_context(parent_type: str, child_type: str) -> str:
    """Formats a parent/child relation for readable validation messages."""

    return f"{parent_type} > {child_type}"
