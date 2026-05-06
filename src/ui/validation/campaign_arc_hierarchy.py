"""Helpers for projecting campaign arc fields into validation hierarchy nodes."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules.campaigns.shared.arc_parser import coerce_arc_list

_ARC_ID_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
_ARC_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label", "arc_name")
_REFERENCE_KEYS = _ARC_ID_KEYS + _ARC_NAME_KEYS + ("ref", "reference", "target")


def build_campaign_arc_nodes(raw_arcs: Any) -> list[dict[str, Any]]:
    """Return validation-ready arc nodes parsed from a campaign ``Arcs`` value."""

    return [
        _build_arc_node(arc, index)
        for index, arc in enumerate(coerce_arc_list(raw_arcs))
        if isinstance(arc, Mapping)
    ]


def _build_arc_node(arc: Mapping[str, Any], index: int) -> dict[str, Any]:
    node = dict(arc)
    identifier = _identifier_for_arc(node, index)
    node["type"] = "arc"
    node["entity_type"] = "arc"
    node["id"] = identifier
    node["name"] = _display_name_for_arc(node, identifier)
    node["scenario_refs"] = _scenario_references_from_arc(node)
    node.pop("scenarios", None)
    return node


def _identifier_for_arc(arc: Mapping[str, Any], index: int) -> str:
    for key in _ARC_ID_KEYS + _ARC_NAME_KEYS:
        value = _clean_text(arc.get(key))
        if value:
            return value
    return f"arc-{index + 1}"


def _display_name_for_arc(arc: Mapping[str, Any], fallback: str) -> str:
    for key in _ARC_NAME_KEYS:
        value = _clean_text(arc.get(key))
        if value:
            return value
    return fallback


def _scenario_references_from_arc(arc: Mapping[str, Any]) -> list[str]:
    raw_scenarios = arc.get("scenarios", arc.get("scenario_refs"))
    if raw_scenarios is None:
        return []

    if isinstance(raw_scenarios, Sequence) and not isinstance(
        raw_scenarios, (str, bytes, bytearray)
    ):
        raw_values = raw_scenarios
    else:
        raw_values = (raw_scenarios,)

    refs: list[str] = []
    for raw_value in raw_values:
        reference = _reference_text(raw_value)
        if reference:
            refs.append(reference)
    return refs


def _reference_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in _REFERENCE_KEYS:
            reference = _clean_text(value.get(key))
            if reference:
                return reference
        return ""
    return _clean_text(value)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
