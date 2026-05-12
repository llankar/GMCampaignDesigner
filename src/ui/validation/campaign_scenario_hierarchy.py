"""Helpers for attaching referenced scenarios to campaign arc nodes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.validation.source_metadata import SOURCE_ITEM_KEY


_SCENARIO_ID_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
_SCENARIO_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label")
ScenarioReferenceIndex = Mapping[str, Sequence[tuple[int, Mapping[str, Any]]]]


def build_scenario_reference_index(
    scenarios: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[tuple[int, dict[str, Any]], ...]]:
    """Index scenario nodes by all user-facing reference keys.

    Arc scenario references can point at a scenario by persisted ID-like values or
    display labels. The validator itself matches exact normalized strings, so the
    hierarchy builder uses the same stripped text values when resolving children.
    """

    index: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for source_index, scenario in enumerate(scenarios):
        for key in _scenario_lookup_keys(scenario):
            index.setdefault(key, []).append((source_index, dict(scenario)))
    return {key: tuple(value) for key, value in index.items()}


def attach_referenced_scenarios_to_arcs(
    arcs: Sequence[dict[str, Any]],
    scenario_index: ScenarioReferenceIndex,
) -> None:
    """Attach resolved scenarios under their referencing arcs in-place.

    Resolved entries are moved from ``arc["scenario_refs"]`` to concrete
    ``arc["scenarios"]`` children. References with no match remain in
    ``scenario_refs`` so the reference validator can still report them as
    missing.
    """

    for arc in arcs:
        unresolved_refs: list[Any] = []
        scenario_children: list[dict[str, Any]] = []
        attached_signatures: set[tuple[int, str, str]] = set()

        for raw_reference in arc.get("scenario_refs", ()):  # keep original shape
            reference = _reference_text(raw_reference)
            matches = scenario_index.get(reference, ()) if reference else ()
            if not matches:
                unresolved_refs.append(raw_reference)
                continue

            for source_index, match in matches:
                signature = _scenario_signature(source_index, match)
                if signature in attached_signatures:
                    continue
                scenario_children.append(_copy_attached_node(match))
                attached_signatures.add(signature)

        if scenario_children:
            arc["scenarios"] = scenario_children
        else:
            arc.pop("scenarios", None)
        arc["scenario_refs"] = unresolved_refs


def _copy_attached_node(node: Mapping[str, Any]) -> dict[str, Any]:
    if SOURCE_ITEM_KEY in node:
        return dict(node)
    return deepcopy(dict(node))


def _scenario_lookup_keys(scenario: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for key in _SCENARIO_ID_KEYS + _SCENARIO_NAME_KEYS:
        value = _clean_text(scenario.get(key))
        if value and value not in keys:
            keys.append(value)
    return tuple(keys)


def _scenario_signature(
    source_index: int, scenario: Mapping[str, Any]
) -> tuple[int, str, str]:
    identifier = _clean_text(scenario.get("id")) or _display_name_for(scenario, "")
    return (
        source_index,
        _clean_text(scenario.get("entity_type")) or "scenario",
        identifier,
    )


def _reference_text(value: Any) -> str:
    if isinstance(value, Mapping):
        reference_keys = _SCENARIO_ID_KEYS + _SCENARIO_NAME_KEYS + (
            "ref",
            "reference",
            "target",
        )
        for key in reference_keys:
            reference = _clean_text(value.get(key))
            if reference:
                return reference
        return ""
    return _clean_text(value)


def _display_name_for(item: Mapping[str, Any], fallback: str) -> str:
    for key in _SCENARIO_NAME_KEYS:
        value = _clean_text(item.get(key))
        if value:
            return value
    return fallback


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
