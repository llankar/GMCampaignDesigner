"""Deterministic cross-reference validation for campaign hierarchies.

The validator intentionally reports issues only. It never mutates the input
hierarchy and leaves correction choices to the interactive layer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .hierarchy_rules import ALLOWED_HIERARCHY_CHILDREN, FIELD_EXPECTED_TYPES
from .issue_models import IssuePayload, IssueType, ValidationIssue

ENTITY_TYPE_KEYS = ("entity_type", "type", "kind", "category", "EntityType", "Type")
ENTITY_ID_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
ENTITY_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label")
MODEL_CHILD_COLLECTIONS: Mapping[str, tuple[str, ...]] = {
    "campaign": ("arcs", "entities"),
    "arc": ("scenarios", "locations"),
    "scenario": (
        "bases",
        "locations",
        "maps",
        "encounters",
        "npcs",
        "pcs",
        "villains",
        "events",
        "creatures",
        "factions",
        "objects",
        "books",
    ),
}
FALLBACK_CHILD_COLLECTIONS = ("children", "items")
SUPPORTED_ENTITY_TYPES = frozenset(
    {
        "arc",
        "base",
        "book",
        "campaign",
        "creature",
        "encounter",
        "event",
        "faction",
        "location",
        "map",
        "npc",
        "object",
        "pc",
        "scenario",
        "villain",
    }
)
STRUCTURAL_KEYS = frozenset(
    {
        "bases",
        "books",
        "children",
        "creatures",
        "encounters",
        "items",
        "events",
        "entities",
        "factions",
        "campaigns",
        "arcs",
        "scenarios",
        "locations",
        "maps",
        "npcs",
        "objects",
        "pcs",
        "villains",
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
    model_child_collections: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(MODEL_CHILD_COLLECTIONS)
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
    parent_node: Mapping[str, Any] | None = None
    collection_name: str = ""
    collection_index: int | None = None

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
class ReferenceTraversalDiagnostics:
    """Internal counters captured during validation traversal."""

    visited_campaigns: int = 0
    visited_arcs: int = 0
    visited_scenarios: int = 0
    visited_references: int = 0
    root_path: tuple[str, ...] = ()

    @property
    def debug_summary_path(self) -> tuple[str, ...]:
        """Return a compact path QA can inspect to confirm traversal work."""

        return (
            "reference-validator",
            f"root={' > '.join(self.root_path) if self.root_path else '<none>'}",
            f"campaigns={self.visited_campaigns}",
            f"arcs={self.visited_arcs}",
            f"scenarios={self.visited_scenarios}",
            f"references={self.visited_references}",
        )

    @property
    def debug_summary(self) -> str:
        """Return a human-readable traversal counter summary."""

        return " | ".join(self.debug_summary_path)


@dataclass(frozen=True)
class ReferenceValidationResult:
    """Full validation result for interactive tools."""

    issues: tuple[ValidationIssue, ...]
    entities: tuple[EntityRecord, ...]
    references: tuple[ReferenceRecord, ...]
    campaign: Mapping[str, Any]
    diagnostics: ReferenceTraversalDiagnostics = field(
        default_factory=ReferenceTraversalDiagnostics
    )

    @property
    def debug_summary_path(self) -> tuple[str, ...]:
        """Expose traversal diagnostics in a stable path-like form for QA."""

        return self.diagnostics.debug_summary_path

    @property
    def debug_summary(self) -> str:
        """Expose traversal diagnostics as a readable debug summary."""

        return self.diagnostics.debug_summary


def validate_references(
    hierarchy: Any,
    *,
    campaign: Mapping[str, Any],
    config: ReferenceValidatorConfig | None = None,
) -> list[ValidationIssue]:
    """Validate references found during a deterministic hierarchy traversal.

    Args:
        hierarchy: Nested campaign data made of mappings/sequences/scalars.
        campaign: Explicit campaign object selected by the user for this run.
        config: Optional validation rules override.

    Returns:
        Ordered validation issues. The order follows the hierarchy traversal and
        reference order inside each source entity.
    """

    return list(
        validate_reference_graph(hierarchy, campaign=campaign, config=config).issues
    )


def validate_reference_graph(
    hierarchy: Any,
    *,
    campaign: Mapping[str, Any],
    config: ReferenceValidatorConfig | None = None,
) -> ReferenceValidationResult:
    """Validate references for an explicit campaign and return traversal metadata."""

    active_config = config or ReferenceValidatorConfig()
    traversal_root = _resolve_traversal_root(hierarchy, campaign)
    entities = tuple(
        _walk_entities(traversal_root, active_config.model_child_collections)
    )
    entity_index = _build_entity_index(entities)
    references = tuple(_walk_references(entities, active_config.field_expected_types))
    diagnostics = _build_traversal_diagnostics(entities, references)
    issues: list[ValidationIssue] = []

    for reference in references:
        if (
            reference.declared_type
            and reference.declared_type != reference.expected_type
        ):
            issues.append(_build_type_issue(reference))
            continue

        candidates = entity_index.get(
            (reference.expected_type, reference.reference_value), ()
        )
        if not candidates:
            issues.append(_build_missing_issue(reference))
            continue
        if len(candidates) > 1:
            issues.append(_build_ambiguous_issue(reference, candidates))
            continue

        target = candidates[0]
        if not _is_valid_hierarchy_position(
            reference,
            target,
            active_config.allowed_hierarchy_children,
        ):
            issues.append(_build_hierarchy_issue(reference, target))

    return ReferenceValidationResult(
        issues=tuple(issues),
        entities=entities,
        references=references,
        campaign=dict(campaign),
        diagnostics=diagnostics,
    )


def _resolve_traversal_root(hierarchy: Any, campaign: Mapping[str, Any]) -> Any:
    """Return the selected campaign node instead of a global registry container."""

    if _mapping_is_campaign(hierarchy):
        if _campaign_matches(hierarchy, campaign) or not _mapping_is_campaign(campaign):
            return hierarchy
        return _campaign_with_defaults(campaign)

    selected_campaign = _find_selected_campaign(hierarchy, campaign)
    if selected_campaign is not None:
        return selected_campaign

    if _mapping_has_supported_entity_record(hierarchy):
        return hierarchy

    if isinstance(campaign, Mapping):
        return _campaign_with_defaults(campaign)

    return hierarchy


def _find_selected_campaign(
    hierarchy: Any,
    campaign: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Find the matching selected campaign within a registry-shaped hierarchy."""

    for candidate in _iter_mapping_nodes(hierarchy):
        if _mapping_is_campaign(candidate) and _campaign_matches(candidate, campaign):
            return candidate
    return None


def _iter_mapping_nodes(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for key in _stable_mapping_keys(value):
            child = value.get(key)
            if isinstance(child, (Mapping, list, tuple)):
                yield from _iter_mapping_nodes(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _iter_mapping_nodes(item)


def _campaign_with_defaults(campaign: Mapping[str, Any]) -> Mapping[str, Any]:
    root = dict(campaign)
    root.setdefault("type", "campaign")
    root.setdefault("entity_type", "campaign")
    identifier = _extract_identifier(root)
    if identifier:
        root.setdefault("id", identifier)
    label = _extract_label(root)
    if label:
        root.setdefault("name", label)
    return root


def _mapping_is_campaign(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and _normalize_text(_first_present(value, ENTITY_TYPE_KEYS)) == "campaign"
    )


def _mapping_has_supported_entity_record(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    entity_type = _normalize_text(_first_present(value, ENTITY_TYPE_KEYS))
    return entity_type in SUPPORTED_ENTITY_TYPES and bool(_extract_identifier(value))


def _campaign_matches(
    candidate: Mapping[str, Any], campaign: Mapping[str, Any]
) -> bool:
    campaign_identifiers = _identity_values(campaign)
    if not campaign_identifiers:
        return True
    return bool(_identity_values(candidate) & campaign_identifiers)


def _identity_values(value: Mapping[str, Any]) -> set[str]:
    return {
        normalized
        for key in ENTITY_ID_KEYS + ENTITY_NAME_KEYS
        if key in value
        for normalized in (_normalize_text(value.get(key)),)
        if normalized
    }


def _build_traversal_diagnostics(
    entities: Sequence[EntityRecord],
    references: Sequence[ReferenceRecord],
) -> ReferenceTraversalDiagnostics:
    counts = Counter(entity.entity_type for entity in entities)
    return ReferenceTraversalDiagnostics(
        visited_campaigns=counts.get("campaign", 0),
        visited_arcs=counts.get("arc", 0),
        visited_scenarios=counts.get("scenario", 0),
        visited_references=len(references),
        root_path=entities[0].path if entities else (),
    )


def _walk_entities(
    root: Any,
    model_child_collections: Mapping[str, tuple[str, ...]],
) -> Iterable[EntityRecord]:
    """Yield selected-campaign entities in explicit model hierarchy order."""

    counter = 0

    def visit(
        value: Any,
        path: tuple[str, ...],
        parent: EntityRecord | None,
    ) -> Iterable[EntityRecord]:
        nonlocal counter
        if isinstance(value, Mapping):
            entity_type = _normalize_text(_first_present(value, ENTITY_TYPE_KEYS))
            identifier = _extract_identifier(value)
            current = parent
            child_base_path = path

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
                    parent_node=parent.node if parent else None,
                    collection_name=_parent_collection_name(parent, path),
                    collection_index=_parent_collection_index(parent, path),
                )
                counter += 1
                yield current
                child_base_path = current.path

            for key in _child_collection_keys(
                entity_type,
                value,
                model_child_collections,
            ):
                child_value = value.get(key, ())
                for child_segment, child in _ordered_collection_items(child_value):
                    yield from visit(
                        child, child_base_path + (key, child_segment), current
                    )
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for segment, item in _ordered_collection_items(value):
                yield from visit(item, path + (segment,), parent)

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
            for ref_index, raw_reference in enumerate(
                _coerce_reference_values(entity.node[field_name])
            ):
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


def _build_hierarchy_issue(
    reference: ReferenceRecord, target: EntityRecord
) -> ValidationIssue:
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
    reference: ReferenceRecord,
    target: EntityRecord,
    allowed_hierarchy_children: Mapping[str, set[str]],
) -> bool:
    if _is_campaign_scenario_catalog_reference(reference, target):
        return _is_descendant_of_source(reference.source, target)

    source = reference.source
    allowed_children = allowed_hierarchy_children.get(source.entity_type, set())
    if target.entity_type not in allowed_children:
        return False
    if (
        target.parent_type == source.entity_type
        and target.parent_identifier == source.identifier
    ):
        return True
    return _is_valid_arc_scenario_ref_membership(reference, target)


def _is_campaign_scenario_catalog_reference(
    reference: ReferenceRecord, target: EntityRecord
) -> bool:
    """Accept campaign scenario lists as references, not containment rules."""

    return (
        reference.field_path in {"campaign.LinkedScenarios", "campaign.scenario_refs"}
        and reference.source.entity_type == "campaign"
        and reference.expected_type == "scenario"
        and target.entity_type == "scenario"
    )


def _is_descendant_of_source(source: EntityRecord, target: EntityRecord) -> bool:
    return target.path[: len(source.path)] == source.path


def _is_valid_arc_scenario_ref_membership(
    reference: ReferenceRecord, target: EntityRecord
) -> bool:
    """Accept graph-level scenarios only when the source arc proves membership."""

    if (
        reference.field_path != "arc.scenario_refs"
        or reference.source.entity_type != "arc"
        or target.entity_type != "scenario"
    ):
        return False

    return _arc_scenario_ref_matches_target(reference, target)


def _arc_scenario_ref_matches_target(
    reference: ReferenceRecord, target: EntityRecord
) -> bool:
    """Return whether this arc reference explicitly identifies the target scenario."""

    target_values = _entity_reference_values(target)
    if reference.reference_value not in target_values:
        return False

    raw_scenario_refs = reference.source.node.get(reference.field_name, ())
    return any(
        _raw_reference_matches_target(reference, raw_reference, target_values)
        for raw_reference in _coerce_reference_values(raw_scenario_refs)
    )


def _raw_reference_matches_target(
    reference: ReferenceRecord,
    raw_reference: Any,
    target_values: frozenset[str],
) -> bool:
    raw_values = _reference_identity_values(raw_reference)
    return reference.reference_value in raw_values and bool(target_values & raw_values)


def _entity_reference_values(entity: EntityRecord) -> frozenset[str]:
    values = {entity.identifier, entity.label}
    values.update(
        _normalize_text(entity.node.get(key))
        for key in ENTITY_ID_KEYS + ENTITY_NAME_KEYS
        if key in entity.node
    )
    return frozenset(value for value in values if value)


def _reference_identity_values(value: Any) -> frozenset[str]:
    if isinstance(value, Mapping):
        reference_keys = ENTITY_ID_KEYS + ENTITY_NAME_KEYS + (
            "ref",
            "reference",
            "target",
        )
        return frozenset(
            normalized
            for key in reference_keys
            if key in value
            for normalized in (_normalize_text(value.get(key)),)
            if normalized
        )
    normalized = _normalize_text(value)
    return frozenset((normalized,)) if normalized else frozenset()


def _split_field_path(field_path: str) -> tuple[str, str]:
    source_type, _, field_name = field_path.partition(".")
    return source_type, field_name


def _parent_collection_name(
    parent: EntityRecord | None,
    path: tuple[str, ...],
) -> str:
    if parent is None:
        return ""
    collection_offset = len(parent.path)
    if len(path) <= collection_offset:
        return ""
    return path[collection_offset]


def _parent_collection_index(
    parent: EntityRecord | None,
    path: tuple[str, ...],
) -> int | None:
    if parent is None:
        return None
    segment_offset = len(parent.path) + 1
    if len(path) <= segment_offset:
        return None
    segment = path[segment_offset]
    if not segment.startswith("[") or not segment.endswith("]"):
        return None
    try:
        return int(segment[1:-1])
    except ValueError:
        return None


def _child_collection_keys(
    entity_type: str,
    value: Mapping[str, Any],
    model_child_collections: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """Return explicit child collections for the current model entity."""

    explicit_keys = model_child_collections.get(entity_type, ())
    fallback_keys = tuple(key for key in FALLBACK_CHILD_COLLECTIONS if key in value)
    if entity_type:
        return tuple(dict.fromkeys(explicit_keys + fallback_keys))
    return tuple(
        key
        for key in _stable_mapping_keys(value)
        if _should_descend_into_key(key, value.get(key))
    )


def _ordered_collection_items(value: Any) -> tuple[tuple[str, Any], ...]:
    """Return collection items in deterministic entity order with stable path segments."""

    if isinstance(value, Mapping):
        items = tuple((str(key), item) for key, item in value.items())
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = tuple((f"[{index}]", item) for index, item in enumerate(value))
    else:
        return ()
    return tuple(
        sorted(items, key=lambda item: _collection_item_sort_key(item[1], item[0]))
    )


def _collection_item_sort_key(value: Any, segment: str) -> tuple[str, str, str, str]:
    if isinstance(value, Mapping):
        entity_type = _normalize_text(_first_present(value, ENTITY_TYPE_KEYS))
        identifier = _extract_identifier(value)
        label = _extract_label(value)
        return (entity_type, identifier, label, segment)
    return (type(value).__name__, _normalize_text(value), "", segment)


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
    return _normalize_text(_first_present(value, ENTITY_ID_KEYS)) or _extract_label(
        value
    )


def _extract_label(value: Mapping[str, Any]) -> str:
    return _normalize_text(_first_present(value, ENTITY_NAME_KEYS))


def _extract_reference_value(value: Any) -> str:
    if isinstance(value, Mapping):
        reference_keys = (
            ENTITY_ID_KEYS + ENTITY_NAME_KEYS + ("ref", "reference", "target")
        )
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
