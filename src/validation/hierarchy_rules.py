"""Reference and hierarchy rules for campaign entities."""

from __future__ import annotations

from typing import Mapping

# Explicit mapping: field path -> expected referenced entity type.
#
# The canonical field names mirror the persisted campaign/scenario templates and
# editor UI.  Legacy ``*_refs`` aliases are kept temporarily so older tests and
# saved validation fixtures can migrate without losing coverage.
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
    # Legacy/test-only aliases retained for safe migration.
    "campaign.arc_refs": "arc",
    "arc.scenario_refs": "scenario",
    "arc.location_refs": "location",
    "scenario.encounter_refs": "encounter",
    "scenario.npc_refs": "npc",
}

# Parent type -> allowed child types
ALLOWED_HIERARCHY_CHILDREN: Mapping[str, set[str]] = {
    "campaign": {"arc"},
    "arc": {"scenario", "location"},
    "scenario": {"encounter", "npc"},
}


def format_hierarchy_context(path: list[str] | tuple[str, ...]) -> str:
    """Formats hierarchy path for UI display (e.g. campaign > arc > scenario)."""

    return " > ".join(path)


def format_parent_child_context(parent_type: str, child_type: str) -> str:
    """Formats a parent/child relation for readable validation messages."""

    return f"{parent_type} > {child_type}"
