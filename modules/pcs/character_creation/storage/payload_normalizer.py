"""Helpers to normalize stored character draft payloads for the UI form."""

from __future__ import annotations

from copy import deepcopy


def _read_equipment_values(payload: dict) -> dict:
    equipment = payload.get("equipment") or {}
    legacy_equipment = payload.get("equipement") or {}
    return {
        "weapon": equipment.get("weapon") or legacy_equipment.get("weapon") or "",
        "armor": equipment.get("armor") or legacy_equipment.get("armor") or "",
        "utility": equipment.get("utility") or legacy_equipment.get("utility") or "",
    }


def _read_equipment_pe_values(payload: dict) -> dict:
    equipment_pe = payload.get("equipment_pe") or {}
    legacy_equipment_pe = payload.get("equipement_pe") or {}
    return {
        "weapon": equipment_pe.get("weapon") or legacy_equipment_pe.get("weapon") or 0,
        "armor": equipment_pe.get("armor") or legacy_equipment_pe.get("armor") or 0,
        "utility": equipment_pe.get("utility") or legacy_equipment_pe.get("utility") or 0,
    }


def normalize_draft_payload_for_form(payload: dict) -> dict:
    """Return a payload copy that always carries form-level equipment fields.

    Older drafts may contain only nested `equipment` dictionaries. The form inputs
    are still keyed by top-level fields (`weapon`, `armor`, etc.), so we mirror
    normalized values there before applying them to widgets.
    """

    normalized = deepcopy(payload)
    equipment = _read_equipment_values(payload)
    equipment_pe = _read_equipment_pe_values(payload)

    normalized.setdefault("equipment", equipment)
    normalized.setdefault("equipment_pe", equipment_pe)
    normalized["weapon"] = equipment["weapon"]
    normalized["armor"] = equipment["armor"]
    normalized["utility"] = equipment["utility"]
    normalized["weapon_pe"] = equipment_pe["weapon"]
    normalized["armor_pe"] = equipment_pe["armor"]
    normalized["utility_pe"] = equipment_pe["utility"]
    return normalized
