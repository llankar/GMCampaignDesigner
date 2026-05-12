"""Format INVALID_HIERARCHY issues with placement-specific guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from modules.helpers.tk_text_safety import LABEL_DISPLAY_LIMIT, safe_display_text
from src.validation import ValidationIssue


@dataclass(frozen=True)
class EntityPathSegment:
    """Parsed entity segment from a validator hierarchy path."""

    entity_type: str
    identifier: str


@dataclass(frozen=True)
class HierarchyPlacement:
    """Best-effort location details for a hierarchy validation target."""

    target: EntityPathSegment | None
    parent: EntityPathSegment | None
    path: tuple[str, ...]


def format_hierarchy_issue_message(issue: ValidationIssue) -> str:
    """Return a focused INVALID_HIERARCHY message for the UI wizard.

    The validator emits INVALID_HIERARCHY when a reference resolves to a target
    that is not valid at the source's position. Older or synthetic issues may
    lack a target path, so this formatter keeps the missing-target wording
    separate from the two misplaced-target cases.
    """

    payload = issue.payload
    source_type = _source_entity_type(payload.source_type, payload.source_path)
    expected_parent = _entity_label(source_type, payload.source_entity)
    target_label = _entity_label(payload.expected_type, payload.referenced_name)
    placement = _target_placement(payload.target_path, payload.candidates)

    if placement.target is None:
        return (
            f'{target_label} is not present under {expected_parent} '
            "in the validation hierarchy."
        )

    if _is_arc_scenario_reference(source_type, payload.field, payload.expected_type):
        return (
            f'{target_label} is listed in arc "{payload.source_entity}", but the '
            "validator did not attach the scenario object under that arc."
        )

    if _is_other_parent(placement.parent, source_type, payload.source_entity):
        actual_parent = _entity_label(
            placement.parent.entity_type,
            placement.parent.identifier,
        )
        return (
            f"{target_label} is attached under {actual_parent}, not "
            f"{expected_parent}, in the validation hierarchy."
        )

    return (
        f"{target_label} exists, but it is not attached under "
        f"{expected_parent} in the validation hierarchy."
    )


def _target_placement(
    target_path: Sequence[str],
    candidates: Sequence[str],
) -> HierarchyPlacement:
    path = tuple(str(part) for part in target_path if str(part))
    if not path:
        path = _path_from_candidates(candidates)
    entity_segments = tuple(
        segment for part in path if (segment := _parse_entity_segment(part)) is not None
    )
    target = entity_segments[-1] if entity_segments else None
    parent = entity_segments[-2] if len(entity_segments) > 1 else None
    return HierarchyPlacement(target=target, parent=parent, path=path)


def _path_from_candidates(candidates: Sequence[str]) -> tuple[str, ...]:
    for candidate in candidates:
        _prefix, separator, raw_path = str(candidate).partition("@")
        if separator and raw_path:
            return tuple(part.strip() for part in raw_path.split(">") if part.strip())
    return ()


def _parse_entity_segment(segment: str) -> EntityPathSegment | None:
    entity_type, separator, identifier = segment.partition(":")
    if not separator or not entity_type.strip() or not identifier.strip():
        return None
    return EntityPathSegment(
        entity_type=entity_type.strip(),
        identifier=identifier.strip(),
    )


def _source_entity_type(source_type: str, source_path: Sequence[str]) -> str:
    normalized_source_type = source_type.strip()
    if normalized_source_type:
        return normalized_source_type

    for segment in reversed(tuple(source_path)):
        parsed = _parse_entity_segment(str(segment))
        if parsed is not None:
            return parsed.entity_type
    return ""


def _is_arc_scenario_reference(
    source_type: str, field: str, expected_type: str
) -> bool:
    return (
        source_type.strip() == "arc"
        and field.strip() == "scenario_refs"
        and expected_type.strip() == "scenario"
    )


def _is_other_parent(
    parent: EntityPathSegment | None,
    source_type: str,
    source_identifier: str,
) -> bool:
    return (
        parent is not None
        and parent.entity_type == source_type
        and parent.identifier != source_identifier
    )


def _entity_label(entity_type: str, identifier: str) -> str:
    normalized_type = entity_type.strip() or "target"
    normalized_identifier = (
        safe_display_text(identifier, max_chars=LABEL_DISPLAY_LIMIT).strip()
        or "<unknown>"
    )
    return f'{normalized_type.capitalize()} "{normalized_identifier}"'
