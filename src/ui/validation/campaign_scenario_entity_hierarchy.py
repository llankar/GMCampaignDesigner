"""Template-derived scenario child entity helpers for campaign validation."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from modules.helpers.template_loader import load_entity_definitions, load_template
from src.validation.source_metadata import SOURCE_ITEM_KEY
from src.validation.field_normalization import (
    FIELD_NORMALIZATION_RULES,
    FieldNormalizationRule,
)
from src.validation.hierarchy_rules import (
    ALLOWED_HIERARCHY_CHILDREN,
    FIELD_EXPECTED_TYPES,
)
from src.validation.reference_validator import (
    MODEL_CHILD_COLLECTIONS,
    ReferenceValidatorConfig,
)


_IDENTIFIER_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label")
_REFERENCE_KEYS = _IDENTIFIER_KEYS + _NAME_KEYS + ("ref", "reference", "target")
_LIST_FIELD_TYPES = {"list", "list_longtext"}
_ENTITY_TYPE_OVERRIDES = {
    "campaigns": "campaign",
    "scenarios": "scenario",
    "places": "location",
    "npcs": "npc",
    "pcs": "pc",
}
_CHILD_COLLECTION_BY_TYPE = {
    "arc": "arcs",
    "base": "bases",
    "book": "books",
    "creature": "creatures",
    "encounter": "encounters",
    "event": "events",
    "faction": "factions",
    "location": "locations",
    "map": "maps",
    "npc": "npcs",
    "object": "objects",
    "pc": "pcs",
    "scenario": "scenarios",
    "villain": "villains",
}

EntityDefinitionsLoader = Callable[[], Mapping[str, Mapping[str, Any]]]
TemplateLoader = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class ScenarioLinkedEntityRule:
    """One linked entity list declared by the scenario template."""

    source_field: str
    linked_type: str
    entity_slug: str
    expected_type: str
    canonical_field: str
    child_collection: str


def discover_scenario_linked_entity_rules(
    entity_wrappers: Mapping[str, Any],
    *,
    template_loader: TemplateLoader = load_template,
    entity_definitions_loader: EntityDefinitionsLoader = load_entity_definitions,
) -> tuple[ScenarioLinkedEntityRule, ...]:
    """Return scenario linked-list rules derived from template JSON metadata."""

    template = template_loader("scenarios")
    try:
        definitions = entity_definitions_loader()
    except Exception:
        definitions = {}

    slug_by_label = _slug_lookup(entity_wrappers, definitions)
    rules: list[ScenarioLinkedEntityRule] = []
    seen_fields: set[str] = set()

    for field in template.get("fields", ()):
        if not isinstance(field, Mapping):
            continue
        field_name = _clean_text(field.get("name"))
        field_type = _clean_text(field.get("type")).lower()
        linked_type = _clean_text(field.get("linked_type"))
        if (
            not field_name
            or field_name in seen_fields
            or field_type not in _LIST_FIELD_TYPES
            or not linked_type
        ):
            continue

        entity_slug = slug_by_label.get(_lookup_key(linked_type)) or _slugify_label(
            linked_type
        )
        expected_type = validator_entity_type_for_slug(entity_slug)
        rules.append(
            ScenarioLinkedEntityRule(
                source_field=field_name,
                linked_type=linked_type,
                entity_slug=entity_slug,
                expected_type=expected_type,
                canonical_field=canonical_reference_field(expected_type),
                child_collection=child_collection_for_entity_type(expected_type),
            )
        )
        seen_fields.add(field_name)

    return tuple(rules)


def campaign_validation_normalization_rules(
    scenario_rules: Sequence[ScenarioLinkedEntityRule],
) -> tuple[FieldNormalizationRule, ...]:
    """Return field normalization rules with scenario lists supplied by metadata."""

    non_scenario_rules = tuple(
        rule for rule in FIELD_NORMALIZATION_RULES if rule.entity_type != "scenario"
    )
    return non_scenario_rules + tuple(
        FieldNormalizationRule(
            "scenario",
            rule.source_field,
            rule.canonical_field,
        )
        for rule in scenario_rules
    )


def campaign_validation_reference_config(
    scenario_rules: Sequence[ScenarioLinkedEntityRule],
) -> ReferenceValidatorConfig:
    """Build validator rules for a campaign scan from scenario template metadata."""

    field_expected_types = {
        field_path: expected_type
        for field_path, expected_type in FIELD_EXPECTED_TYPES.items()
        if not field_path.startswith("scenario.")
    }
    for rule in scenario_rules:
        field_expected_types[f"scenario.{rule.source_field}"] = rule.expected_type
        field_expected_types[f"scenario.{rule.canonical_field}"] = rule.expected_type

    allowed_children = {
        key: set(value) for key, value in ALLOWED_HIERARCHY_CHILDREN.items()
    }
    allowed_children["scenario"] = {
        rule.expected_type for rule in scenario_rules if rule.expected_type
    }

    child_collections = dict(MODEL_CHILD_COLLECTIONS)
    child_collections["scenario"] = tuple(
        dict.fromkeys(rule.child_collection for rule in scenario_rules)
    )

    return ReferenceValidatorConfig(
        field_expected_types=field_expected_types,
        allowed_hierarchy_children=allowed_children,
        model_child_collections=child_collections,
    )


def attach_referenced_entities_to_scenarios(
    scenarios: Sequence[MutableMapping[str, Any]],
    entity_nodes_by_slug: Mapping[str, Sequence[tuple[int, Mapping[str, Any]]]],
    scenario_rules: Sequence[ScenarioLinkedEntityRule],
) -> frozenset[tuple[str, int, str, str]]:
    """Attach resolved scenario entity refs under their scenario nodes in-place."""

    indexes = _build_entity_reference_indexes(entity_nodes_by_slug)
    attached_signatures: set[tuple[str, int, str, str]] = set()

    for scenario in scenarios:
        for rule in scenario_rules:
            raw_refs = scenario.get(rule.canonical_field, ())
            unresolved_refs: list[Any] = []
            child_collection = _existing_child_collection(
                scenario,
                rule.child_collection,
            )
            local_identities = {
                _identity_signature(rule.entity_slug, child)
                for child in child_collection
                if isinstance(child, Mapping)
            }

            for raw_reference in _coerce_reference_values(raw_refs):
                reference = _reference_text(raw_reference)
                if not reference:
                    continue
                matches = (
                    indexes.get(rule.entity_slug, {}).get(reference, ())
                )
                if not matches:
                    unresolved_refs.append(raw_reference)
                    continue

                for source_index, match in matches:
                    signature = _node_signature(rule.entity_slug, source_index, match)
                    identity = _identity_signature(rule.entity_slug, match)
                    if identity in local_identities:
                        continue
                    child_collection.append(_copy_attached_node(match))
                    local_identities.add(identity)
                    attached_signatures.add(signature)

            if child_collection:
                scenario[rule.child_collection] = child_collection
            if unresolved_refs:
                scenario[rule.canonical_field] = unresolved_refs
            else:
                scenario.pop(rule.canonical_field, None)

    return frozenset(attached_signatures)


def _copy_attached_node(node: Mapping[str, Any]) -> dict[str, Any]:
    if SOURCE_ITEM_KEY in node:
        return dict(node)
    return deepcopy(dict(node))


def entity_source_signature(
    slug: str,
    source_index: int,
    entity: Mapping[str, Any],
) -> tuple[str, int, str, str]:
    """Return the signature used to decide whether a flat entity was attached."""

    return _node_signature(slug, source_index, entity)


def validator_entity_type_for_slug(slug: str) -> str:
    """Return the validator entity type for an entity wrapper/template slug."""

    normalized = _lookup_key(slug)
    if normalized in _ENTITY_TYPE_OVERRIDES:
        return _ENTITY_TYPE_OVERRIDES[normalized]
    if normalized.endswith("ies"):
        return f"{normalized[:-3]}y"
    if normalized.endswith("s"):
        return normalized[:-1]
    return normalized


def canonical_reference_field(entity_type: str) -> str:
    """Return the canonical reference field name for a validator entity type."""

    return f"{entity_type}_refs"


def child_collection_for_entity_type(entity_type: str) -> str:
    """Return the validation child collection for a validator entity type."""

    return _CHILD_COLLECTION_BY_TYPE.get(entity_type, f"{entity_type}s")


def _build_entity_reference_indexes(
    entity_nodes_by_slug: Mapping[str, Sequence[tuple[int, Mapping[str, Any]]]],
) -> dict[str, dict[str, tuple[tuple[int, Mapping[str, Any]], ...]]]:
    indexes: dict[str, dict[str, list[tuple[int, Mapping[str, Any]]]]] = {}
    for slug, nodes in entity_nodes_by_slug.items():
        slug_index: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
        for source_index, node in nodes:
            for key in _node_lookup_keys(node):
                slug_index.setdefault(key, []).append((source_index, node))
        indexes[slug] = slug_index
    return {
        slug: {key: tuple(value) for key, value in slug_index.items()}
        for slug, slug_index in indexes.items()
    }


def _node_lookup_keys(node: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for key in _IDENTIFIER_KEYS + _NAME_KEYS:
        value = _clean_text(node.get(key))
        if value and value not in keys:
            keys.append(value)
    return tuple(keys)


def _node_signature(
    slug: str,
    source_index: int,
    node: Mapping[str, Any],
) -> tuple[str, int, str, str]:
    entity_type = _clean_text(node.get("entity_type")) or _clean_text(node.get("type"))
    identifier = _clean_text(node.get("id")) or _display_name_for(node, "")
    return (
        slug,
        source_index,
        entity_type or validator_entity_type_for_slug(slug),
        identifier,
    )


def _identity_signature(
    slug: str,
    node: Mapping[str, Any],
) -> tuple[str, str]:
    identifier = _clean_text(node.get("id")) or _display_name_for(node, "")
    return (validator_entity_type_for_slug(slug), identifier)


def _existing_child_collection(
    scenario: MutableMapping[str, Any],
    collection_name: str,
) -> list[Any]:
    current = scenario.get(collection_name)
    if isinstance(current, list):
        return current
    if isinstance(current, tuple):
        return list(current)
    return []


def _slug_lookup(
    entity_wrappers: Mapping[str, Any],
    definitions: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for slug in sorted(set(entity_wrappers) | set(definitions)):
        labels = {
            slug,
            slug.replace("_", " "),
            slug.replace("_", " ").title(),
            _clean_text(definitions.get(slug, {}).get("label")),
        }
        for label in labels:
            if label:
                lookup.setdefault(_lookup_key(label), slug)
    return lookup


def _slugify_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def _reference_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in _REFERENCE_KEYS:
            reference = _clean_text(value.get(key))
            if reference:
                return reference
        return ""
    return _clean_text(value)


def _display_name_for(item: Mapping[str, Any], fallback: str) -> str:
    for key in _NAME_KEYS:
        value = _clean_text(item.get(key))
        if value:
            return value
    return fallback


def _coerce_reference_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return (value,)


def _lookup_key(value: str) -> str:
    return value.strip().lower()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
