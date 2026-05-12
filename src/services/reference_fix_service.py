"""Services for applying interactive reference fixes.

The validation layer only reports reference issues.  This module owns the small,
UI-friendly mutations needed after a user chooses how to resolve one issue:
remap the reference, remove it, or link it to a newly created entity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, MutableMapping, MutableSequence

from src.validation.hierarchy_rules import ALLOWED_HIERARCHY_CHILDREN
from src.validation.source_metadata import source_field_for, source_item_for
from src.validation.reference_validator import EntityRecord, ReferenceRecord


@dataclass(frozen=True)
class ReferenceActionResult:
    """Single action-return contract shared by all reference fix operations.

    Attributes:
        success: ``True`` when the requested action was applied.
        changes_applied: Human-readable, deterministic descriptions of each
            mutation performed. Empty when no mutation happened.
        ui_message: Short message intended for dialogs, toasts, or status bars.
    """

    success: bool
    changes_applied: tuple[str, ...] = field(default_factory=tuple)
    ui_message: str = ""

    @classmethod
    def ok(cls, ui_message: str, *changes_applied: str) -> "ReferenceActionResult":
        """Build a successful action result."""

        return cls(
            success=True,
            changes_applied=tuple(change for change in changes_applied if change),
            ui_message=ui_message,
        )

    @classmethod
    def error(cls, ui_message: str) -> "ReferenceActionResult":
        """Build a failed action result without applied changes."""

        return cls(success=False, changes_applied=(), ui_message=ui_message)


class ReferenceFixAction(str, Enum):
    """Supported interactive reference correction actions."""

    ATTACH = "attach"
    REMAP = "remap"
    REMOVE = "remove"
    LINK_CREATED = "link_created"


class ReferenceFixService:
    """Apply user-selected fixes to mutable reference fields.

    The service accepts ``ReferenceRecord`` instances returned by
    ``validate_reference_graph`` and mutates the source entity node in place.
    It supports both scalar reference fields and list/tuple-style reference
    collections. Mapping references keep their original shape where possible:
    identifiers are updated in an existing ``id``/``ref``/``target``/``name`` key
    and declared types are synchronized when a type key already exists.
    """

    def remap_reference(
        self,
        reference: ReferenceRecord,
        target: EntityRecord | MutableMapping[str, Any] | str,
    ) -> ReferenceActionResult:
        """Remap one reference occurrence to the chosen target."""

        target_identifier = _extract_target_identifier(target)
        if not target_identifier:
            return ReferenceActionResult.error("Cannot remap: invalid target.")

        target_type = _extract_target_type(target)
        updated = _replace_reference_value(reference, target_identifier, target_type)
        if not updated:
            return ReferenceActionResult.error(
                "Cannot remap: reference not found or not editable."
            )

        return ReferenceActionResult.ok(
            f'Reference remapped to "{target_identifier}".',
            _format_reference_change(
                ReferenceFixAction.REMAP,
                reference,
                target_identifier,
            ),
        )

    def remove_reference(self, reference: ReferenceRecord) -> ReferenceActionResult:
        """Remove one reference occurrence from its source field."""

        removed = _remove_reference_value(reference)
        if not removed:
            return ReferenceActionResult.error(
                "Cannot remove: reference not found or not editable."
            )

        return ReferenceActionResult.ok(
            f'Reference "{reference.reference_value}" removed.',
            _format_reference_change(ReferenceFixAction.REMOVE, reference),
        )

    def can_attach_existing_entity(
        self,
        reference: ReferenceRecord,
        target: EntityRecord | None,
    ) -> bool:
        """Return whether an existing target can be moved under the reference source."""

        return _can_attach_existing_entity(reference, target)

    def attach_existing_entity(
        self,
        reference: ReferenceRecord,
        target: EntityRecord | None,
    ) -> ReferenceActionResult:
        """Move an existing target entity under the source's child collection."""

        if not _can_attach_existing_entity(reference, target):
            return ReferenceActionResult.error(
                "Cannot attach: target cannot be safely placed under this source."
            )
        assert target is not None

        source_node = reference.source.node
        target_node = target.node
        if not isinstance(source_node, MutableMapping) or not isinstance(
            target_node, MutableMapping
        ):
            return ReferenceActionResult.error(
                "Cannot attach: source or target is not editable."
            )

        collection_name = _child_collection_name(reference.expected_type)
        source_collection = _editable_collection(source_node, collection_name)
        origin_collection = _origin_collection(target)
        if source_collection is None or origin_collection is None:
            return ReferenceActionResult.error(
                "Cannot attach: source or target collection is not editable."
            )
        if source_collection is origin_collection:
            return ReferenceActionResult.error(
                "Cannot attach: target is already in the source collection."
            )
        if not _collection_contains_identity(origin_collection, target_node):
            return ReferenceActionResult.error(
                "Cannot attach: target was not found in its current collection."
            )
        if _collection_contains_equivalent_entity(source_collection, target):
            return ReferenceActionResult.error(
                "Cannot attach: equivalent target is already in the source collection."
            )

        removed = _remove_child_by_identity(origin_collection, target_node)
        if not removed:
            return ReferenceActionResult.error(
                "Cannot attach: target was not found in its current collection."
            )
        _mirror_node_field(target.parent_node, target.collection_name, origin_collection)
        source_collection.append(target_node)
        _mirror_node_field(source_node, collection_name, source_collection)

        return ReferenceActionResult.ok(
            f'Entity "{target.identifier}" attached under "{reference.source.identifier}".',
            _format_attach_change(reference, target, collection_name),
        )

    def link_created_entity(
        self,
        reference: ReferenceRecord,
        new_entity: EntityRecord | MutableMapping[str, Any],
        *,
        attach_to_source: bool = True,
    ) -> ReferenceActionResult:
        """Link a reference to a newly created entity.

        Args:
            reference: The reference occurrence to resolve.
            new_entity: Newly created entity record or mutable entity mapping.
            attach_to_source: When ``True`` and ``new_entity`` is a mutable
                mapping, append it to the source entity child collection matching
                ``reference.expected_type`` before remapping the reference.
        """

        target_identifier = _extract_target_identifier(new_entity)
        if not target_identifier:
            return ReferenceActionResult.error("Cannot link: created entity is invalid.")

        changes: list[str] = []
        if attach_to_source and isinstance(new_entity, MutableMapping):
            attach_change = _attach_child_entity(reference, new_entity)
            if attach_change:
                changes.append(attach_change)

        target_type = _extract_target_type(new_entity) or reference.expected_type
        updated = _replace_reference_value(reference, target_identifier, target_type)
        if not updated:
            return ReferenceActionResult.error(
                "Cannot link: reference not found or not editable."
            )

        changes.append(
            _format_reference_change(
                ReferenceFixAction.LINK_CREATED,
                reference,
                target_identifier,
            )
        )
        return ReferenceActionResult.ok(
            f'Created entity "{target_identifier}" linked.',
            *changes,
        )


_IDENTIFIER_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label")
_REFERENCE_KEYS = _IDENTIFIER_KEYS + _NAME_KEYS + ("ref", "reference", "target")
_TYPE_KEYS = ("entity_type", "type", "kind", "category", "EntityType", "Type")
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


def _replace_reference_value(
    reference: ReferenceRecord,
    target_identifier: str,
    target_type: str | None,
) -> bool:
    source_node = reference.source.node
    if not isinstance(source_node, MutableMapping) or reference.field_name not in source_node:
        return False

    raw_value = source_node[reference.field_name]
    index = _editable_reference_index(reference, raw_value)
    if _is_mutable_reference_collection(raw_value):
        if index is None:
            return False
        raw_value[index] = _updated_reference_object(
            raw_value[index],
            target_identifier,
            target_type,
        )
        _mirror_reference_field(reference, raw_value)
        return True

    source_node[reference.field_name] = _updated_reference_object(
        raw_value,
        target_identifier,
        target_type,
    )
    _mirror_reference_field(reference, source_node[reference.field_name])
    return True


def _remove_reference_value(reference: ReferenceRecord) -> bool:
    source_node = reference.source.node
    if not isinstance(source_node, MutableMapping) or reference.field_name not in source_node:
        return False

    raw_value = source_node[reference.field_name]
    index = _editable_reference_index(reference, raw_value)
    if _is_mutable_reference_collection(raw_value):
        if index is None:
            return False
        del raw_value[index]
        _mirror_reference_field(reference, raw_value)
        return True

    del source_node[reference.field_name]
    _remove_mirrored_reference_field(reference)
    return True


def _editable_reference_index(reference: ReferenceRecord, raw_value: Any) -> int | None:
    index = _reference_index(reference)
    if (
        index is not None
        and _is_mutable_reference_collection(raw_value)
        and 0 <= index < len(raw_value)
        and _reference_value_matches(raw_value[index], reference.reference_value)
    ):
        return index
    if not _is_mutable_reference_collection(raw_value):
        return None
    for fallback_index, candidate in enumerate(raw_value):
        if _reference_value_matches(candidate, reference.reference_value):
            return fallback_index
    return None


def _reference_value_matches(value: Any, expected: str) -> bool:
    if isinstance(value, Mapping):
        return _normalize(_first_present(value, _REFERENCE_KEYS)) == expected
    return _normalize(value) == expected


def _mirror_reference_field(reference: ReferenceRecord, value: Any) -> None:
    _mirror_node_field(reference.source.node, reference.field_name, value)


def _remove_mirrored_reference_field(reference: ReferenceRecord) -> None:
    source_node = reference.source.node
    if not isinstance(source_node, Mapping):
        return
    source_item = source_item_for(source_node)
    if source_item is None:
        return
    source_item.pop(source_field_for(source_node, reference.field_name), None)


def _mirror_node_field(node: Mapping[str, Any] | None, field_name: str, value: Any) -> None:
    if not isinstance(node, Mapping):
        return
    source_item = source_item_for(node)
    if source_item is None:
        return
    source_item[source_field_for(node, field_name)] = value


def _is_mutable_reference_collection(value: Any) -> bool:
    return isinstance(value, MutableSequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    )


def _updated_reference_object(value: Any, target_identifier: str, target_type: str | None) -> Any:
    if not isinstance(value, MutableMapping):
        return target_identifier

    updated = dict(value)
    reference_key = _first_present_key(updated, _REFERENCE_KEYS) or "ref"
    updated[reference_key] = target_identifier

    type_key = _first_present_key(updated, _TYPE_KEYS)
    if type_key and target_type:
        updated[type_key] = target_type
    return updated


def _attach_child_entity(
    reference: ReferenceRecord,
    new_entity: MutableMapping[str, Any],
) -> str:
    source_node = reference.source.node
    if not isinstance(source_node, MutableMapping):
        return ""

    collection_name = _child_collection_name(reference.expected_type)
    collection = source_node.setdefault(collection_name, [])
    if not isinstance(collection, MutableSequence):
        return ""
    if any(item is new_entity for item in collection):
        return ""

    collection.append(new_entity)
    _mirror_node_field(source_node, collection_name, collection)
    return f"{collection_name}: entity added"


def _can_attach_existing_entity(
    reference: ReferenceRecord,
    target: EntityRecord | None,
) -> bool:
    if target is None:
        return False
    if target.entity_type != reference.expected_type:
        return False
    if not _source_allows_child_type(reference.source.entity_type, target.entity_type):
        return False
    if not isinstance(reference.source.node, MutableMapping):
        return False
    if not isinstance(target.node, MutableMapping):
        return False
    if target.parent_node is None or not target.collection_name:
        return False

    collection_name = _child_collection_name(target.entity_type)
    if not _source_collection_is_editable(reference.source.node, collection_name):
        return False
    source_collection = _existing_collection(reference.source.node, collection_name)
    origin_collection = _origin_collection(target)
    if origin_collection is None:
        return False
    if not _collection_contains_identity(origin_collection, target.node):
        return False
    if (
        source_collection is not None
        and _collection_contains_equivalent_entity(source_collection, target)
    ):
        return False
    return source_collection is None or source_collection is not origin_collection


def _source_allows_child_type(source_type: str, child_type: str) -> bool:
    return child_type in ALLOWED_HIERARCHY_CHILDREN.get(source_type, set())


def _child_collection_name(entity_type: str) -> str:
    return _CHILD_COLLECTION_BY_TYPE.get(entity_type, f"{entity_type}s")


def _editable_collection(
    source_node: MutableMapping[str, Any],
    collection_name: str,
) -> MutableSequence[Any] | None:
    collection = source_node.setdefault(collection_name, [])
    if not isinstance(collection, MutableSequence):
        return None
    return collection


def _source_collection_is_editable(
    source_node: MutableMapping[str, Any],
    collection_name: str,
) -> bool:
    collection = source_node.get(collection_name)
    return collection is None or isinstance(collection, MutableSequence)


def _existing_collection(
    source_node: MutableMapping[str, Any],
    collection_name: str,
) -> MutableSequence[Any] | None:
    collection = source_node.get(collection_name)
    if isinstance(collection, MutableSequence):
        return collection
    return None


def _origin_collection(target: EntityRecord) -> MutableSequence[Any] | None:
    parent_node = target.parent_node
    if not isinstance(parent_node, Mapping) or not target.collection_name:
        return None
    collection = parent_node.get(target.collection_name)
    if not isinstance(collection, MutableSequence):
        return None
    return collection


def _remove_child_by_identity(
    collection: MutableSequence[Any],
    target_node: MutableMapping[str, Any],
) -> bool:
    for index, item in enumerate(collection):
        if item is target_node:
            del collection[index]
            return True
    return False


def _collection_contains_identity(
    collection: MutableSequence[Any],
    target_node: MutableMapping[str, Any],
) -> bool:
    return any(item is target_node for item in collection)


def _collection_contains_equivalent_entity(
    collection: MutableSequence[Any],
    target: EntityRecord,
) -> bool:
    target_values = _entity_identity_values(target.node) | {
        target.identifier,
        target.label,
    }
    target_values.discard("")
    for item in collection:
        if item is target.node:
            return True
        if not isinstance(item, Mapping):
            continue
        item_type = _extract_target_type(item)
        if item_type and item_type != target.entity_type:
            continue
        if _entity_identity_values(item) & target_values:
            return True
    return False


def _entity_identity_values(value: Mapping[str, Any]) -> set[str]:
    return {
        normalized
        for key in _IDENTIFIER_KEYS + _NAME_KEYS
        if key in value
        for normalized in (_normalize(value.get(key)),)
        if normalized
    }


def _extract_target_identifier(target: EntityRecord | MutableMapping[str, Any] | str) -> str:
    if isinstance(target, EntityRecord):
        return target.identifier
    if isinstance(target, str):
        return target.strip()
    if isinstance(target, MutableMapping):
        return _normalize(_first_present(target, _IDENTIFIER_KEYS + _NAME_KEYS))
    return ""


def _extract_target_type(target: EntityRecord | MutableMapping[str, Any] | str) -> str | None:
    if isinstance(target, EntityRecord):
        return target.entity_type
    if isinstance(target, MutableMapping):
        return _normalize(_first_present(target, _TYPE_KEYS)) or None
    return None


def _reference_index(reference: ReferenceRecord) -> int | None:
    if not reference.path:
        return None
    raw_index = reference.path[-1]
    if not raw_index.startswith("[") or not raw_index.endswith("]"):
        return None
    try:
        return int(raw_index[1:-1])
    except ValueError:
        return None


def _format_reference_change(
    action: ReferenceFixAction,
    reference: ReferenceRecord,
    target_identifier: str = "",
) -> str:
    location = f"{reference.source.identifier}.{reference.field_name}"
    if action is ReferenceFixAction.REMOVE:
        return f"{location}: reference removed"
    return f"{location}: {reference.reference_value} -> {target_identifier}"


def _format_attach_change(
    reference: ReferenceRecord,
    target: EntityRecord,
    collection_name: str,
) -> str:
    return (
        f"{reference.source.identifier}.{collection_name}: "
        f"{target.identifier} attached"
    )


def _first_present(value: MutableMapping[str, Any], keys: tuple[str, ...]) -> Any:
    key = _first_present_key(value, keys)
    return value[key] if key else None


def _first_present_key(value: MutableMapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in value:
            return key
    return None


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
