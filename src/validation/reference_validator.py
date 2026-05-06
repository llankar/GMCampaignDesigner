"""Deterministic cross-reference validation for campaign hierarchies.

The validator intentionally reports issues only. It never mutates the input
hierarchy and leaves correction choices to the interactive layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .hierarchy_rules import ALLOWED_HIERARCHY_CHILDREN, FIELD_EXPECTED_TYPES
from .issue_models import IssuePayload, IssueType, ValidationIssue

ENTITY_TYPE_KEYS = ("entity_type", "type", "kind", "category", "EntityType", "Type")
ENTITY_ID_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
ENTITY_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label")
STRUCTURAL_KEYS = frozenset(
    {
        "children",
        "items",
        "entities",
        "campaigns",
        "arcs",
        "scenarios",
        "locations",
        "encounters",
        "npcs",
    }
)


@dataclass(frozen=True)
class ReferenceValidatorConfig:
    """Rules used by :func:`validate_references`."""

    field_expected_types: Mapping[str, str] = field(
        default_factory=lambda: dict(FIELD_EXPECTED_TYPES)
    )
    allowed_hierarchy_children: Mapping[str, set[str]] = field(
        default_factory=lambda: {
            key: set(value) for key, value in ALLOWED_HIERARCHY_CHILDREN.items()
        }
    )


@dataclass(frozen=True)
class EntityRecord:
    """Stable metadata collected for one entity in the hierarchy."""

    entity_type: str
    identifier: str
    label: str
    node: Mapping[str, Any]
    path: tuple[str, ...]
    parent_path: tuple[str, ...]
    parent_type: str | None
    parent_identifier: str | None
    order: int

    @property
    def signature(self) -> tuple[str, str]:
        """Return the canonical type/identifier signature for this entity."""

        return (self.entity_type, self.identifier)


@dataclass(frozen=True)
class ReferenceRecord:
    """Stable metadata collected for one reference occurrence."""

    source: EntityRecord
    field_name: str
    field_path: str
    expected_type: str
    reference_value: str
    declared_type: str | None
    path: tuple[str, ...]
    order: int


@dataclass(frozen=True)
class ReferenceValidationResult:
    """Full validation result for interactive tools."""

    issues: tuple[ValidationIssue, ...]
    entities: tuple[EntityRecord, ...]
    references: tuple[ReferenceRecord, ...]


def validate_references(
    hierarchy: Any,
    *,
    config: ReferenceValidatorConfig | None = None,
) -> list[ValidationIssue]:
    """Validate references found during a deterministic hierarchy traversal.

    Args:
        hierarchy: Nested campaign data made of mappings/sequences/scalars.
        config: Optional validation rules override.

    Returns:
        Ordered validation issues. The order follows the hierarchy traversal and
        reference order inside each source entity.
    """

    return list(validate_reference_graph(hierarchy, config=config).issues)


def validate_reference_graph(
    hierarchy: Any,
    *,
    config: ReferenceValidatorConfig | None = None,
) -> ReferenceValidationResult:
    """Validate references and return issues plus traversal metadata."""

    active_config = config or ReferenceValidatorConfig()
    entities = tuple(_walk_entities(hierarchy))
    entity_index = _build_entity_index(entities)
    references = tuple(_walk_references(entities, active_config.field_expected_types))
    issues: list[ValidationIssue] = []

    for reference in references:
        if reference.declared_type and reference.declared_type != reference.expected_type:
            issues.append(_build_type_issue(reference))
            continue

        candidates = entity_index.get((reference.expected_type, reference.reference_value), ())
        if not candidates:
            issues.append(_build_missing_issue(reference))
            continue
        if len(candidates) > 1:
            issues.append(_build_ambiguous_issue(reference, candidates))
            continue

        target = candidates[0]
        if not _is_valid_hierarchy_position(
            reference.source,
            target,
            active_config.allowed_hierarchy_children,
        ):
            issues.append(_build_hierarchy_issue(reference, target))

    return ReferenceValidationResult(issues=tuple(issues), entities=entities, references=references)


def _walk_entities(root: Any) -> Iterable[EntityRecord]:
    """Yield entities in stable hierarchy order."""

    counter = 0

    def visit(value: Any, path: tuple[str, ...], parent: EntityRecord | None) -> Iterable[EntityRecord]:
        nonlocal counter
        current_parent = parent
        if isinstance(value, Mapping):
            entity_type = _normalize_text(_first_present(value, ENTITY_TYPE_KEYS))
            identifier = _extract_identifier(value)
            if entity_type and identifier:
                label = _extract_label(value) or identifier
                current = EntityRecord(
                    entity_type=entity_type,
                    identifier=identifier,
                    label=label,
                    node=value,
                    path=path + (f"{entity_type}:{identifier}",),
                    parent_path=parent.path if parent else (),
                    parent_type=parent.entity_type if parent else None,
                    parent_identifier=parent.identifier if parent else None,
                    order=counter,
                )
                counter += 1
                yield current
                current_parent = current
                child_base_path = current.path
            else:
                child_base_path = path

            for key in _stable_mapping_keys(value):
                if _should_descend_into_key(key, value.get(key)):
                    yield from visit(value[key], child_base_path + (str(key),), current_parent)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, item in enumerate(value):
                yield from visit(item, path + (f"[{index}]",), current_parent)

    yield from visit(root, (), None)


def _walk_references(
    entities: Sequence[EntityRecord],
    field_expected_types: Mapping[str, str],
) -> Iterable[ReferenceRecord]:
    """Yield reference records in entity traversal order, then rule order."""

    order = 0
    rules = sorted(field_expected_types.items(), key=lambda item: item[0])
    for entity in entities:
        for field_path, expected_type in rules:
            source_type, field_name = _split_field_path(field_path)
            if source_type != entity.entity_type or field_name not in entity.node:
                continue
            for ref_index, raw_reference in enumerate(_coerce_reference_values(entity.node[field_name])):
                reference_value = _extract_reference_value(raw_reference)
                if not reference_value:
                    continue
                declared_type = _extract_reference_type(raw_reference)
                yield ReferenceRecord(
                    source=entity,
                    field_name=field_name,
                    field_path=field_path,
                    expected_type=expected_type,
                    reference_value=reference_value,
                    declared_type=declared_type,
                    path=entity.path + (field_name, f"[{ref_index}]"),
                    order=order,
                )
                order += 1


def _build_entity_index(
    entities: Sequence[EntityRecord],
) -> dict[tuple[str, str], tuple[EntityRecord, ...]]:
    index: dict[tuple[str, str], list[EntityRecord]] = {}
    for entity in entities:
        identifiers = {entity.identifier, entity.label}
        identifiers.update(
            _normalize_text(entity.node.get(key))
            for key in ENTITY_NAME_KEYS
            if key in entity.node
        )
        for identifier in sorted(value for value in identifiers if value):
            index.setdefault((entity.entity_type, identifier), []).append(entity)
    return {
        key: tuple(sorted(value, key=lambda entity: entity.order))
        for key, value in index.items()
    }


def _build_missing_issue(reference: ReferenceRecord) -> ValidationIssue:
    return ValidationIssue(
        issue_type=IssueType.MISSING_REFERENCE,
        payload=IssuePayload(
            source_entity=reference.source.identifier,
            field=reference.field_name,
            referenced_name=reference.reference_value,
            expected_type=reference.expected_type,
            candidates=(),
            hierarchy_path=reference.path,
            source_type=reference.source.entity_type,
            source_path=reference.source.path,
            resolution_hint=(
                "Create the missing target, rename the reference, or remove it."
            ),
        ),
    )


def _build_type_issue(reference: ReferenceRecord) -> ValidationIssue:
    return ValidationIssue(
        issue_type=IssueType.INVALID_REFERENCE_TYPE,
        payload=IssuePayload(
            source_entity=reference.source.identifier,
            field=reference.field_name,
            referenced_name=reference.reference_value,
            expected_type=reference.expected_type,
            candidates=(reference.declared_type or "",),
            hierarchy_path=reference.path,
            source_type=reference.source.entity_type,
            actual_type=reference.declared_type or "",
            source_path=reference.source.path,
            resolution_hint=(
                "Change the reference type or move it to a field expecting this type."
            ),
        ),
    )


def _build_ambiguous_issue(
    reference: ReferenceRecord,
    candidates: Sequence[EntityRecord],
) -> ValidationIssue:
    return ValidationIssue(
        issue_type=IssueType.AMBIGUOUS_REFERENCE,
        payload=IssuePayload(
            source_entity=reference.source.identifier,
            field=reference.field_name,
            referenced_name=reference.reference_value,
            expected_type=reference.expected_type,
            candidates=tuple(_format_candidate(candidate) for candidate in candidates),
            hierarchy_path=reference.path,
            source_type=reference.source.entity_type,
            source_path=reference.source.path,
            resolution_hint="Choose one candidate explicitly or rename duplicates.",
        ),
    )


def _build_hierarchy_issue(reference: ReferenceRecord, target: EntityRecord) -> ValidationIssue:
    return ValidationIssue(
        issue_type=IssueType.INVALID_HIERARCHY,
        payload=IssuePayload(
            source_entity=reference.source.identifier,
            field=reference.field_name,
            referenced_name=reference.reference_value,
            expected_type=reference.expected_type,
            candidates=(_format_candidate(target),),
            hierarchy_path=reference.path,
            source_type=reference.source.entity_type,
            actual_type=target.entity_type,
            source_path=reference.source.path,
            target_path=target.path,
            resolution_hint=(
                "Move the target under the source entity or remove the cross-hierarchy reference."
            ),
        ),
    )


def _is_valid_hierarchy_position(
    source: EntityRecord,
    target: EntityRecord,
    allowed_hierarchy_children: Mapping[str, set[str]],
) -> bool:
    allowed_children = allowed_hierarchy_children.get(source.entity_type, set())
    if target.entity_type not in allowed_children:
        return False
    return target.parent_type == source.entity_type and target.parent_identifier == source.identifier


def _split_field_path(field_path: str) -> tuple[str, str]:
    source_type, _, field_name = field_path.partition(".")
    return source_type, field_name


def _stable_mapping_keys(value: Mapping[str, Any]) -> list[str]:
    structural = sorted(key for key in value if key in STRUCTURAL_KEYS)
    remaining = sorted(key for key in value if key not in STRUCTURAL_KEYS)
    return structural + remaining


def _should_descend_into_key(key: str, value: Any) -> bool:
    if key in STRUCTURAL_KEYS:
        return True
    if key.endswith("_refs") or key in {"references", "links"}:
        return False
    return isinstance(value, (Mapping, list, tuple))


def _coerce_reference_values(value: Any) -> Iterable[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        yield from value
    else:
        yield value


def _extract_identifier(value: Mapping[str, Any]) -> str:
    return _normalize_text(_first_present(value, ENTITY_ID_KEYS)) or _extract_label(value)


def _extract_label(value: Mapping[str, Any]) -> str:
    return _normalize_text(_first_present(value, ENTITY_NAME_KEYS))


def _extract_reference_value(value: Any) -> str:
    if isinstance(value, Mapping):
        reference_keys = ENTITY_ID_KEYS + ENTITY_NAME_KEYS + ("ref", "reference", "target")
        return _normalize_text(_first_present(value, reference_keys))
    return _normalize_text(value)


def _extract_reference_type(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return _normalize_text(_first_present(value, ENTITY_TYPE_KEYS)) or None
    return None


def _first_present(value: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _format_candidate(entity: EntityRecord) -> str:
    return f"{entity.entity_type}:{entity.identifier}@{' > '.join(entity.path)}"
