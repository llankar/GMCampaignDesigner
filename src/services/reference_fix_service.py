"""Services for applying interactive reference fixes.

The validation layer only reports reference issues.  This module owns the small,
UI-friendly mutations needed after a user chooses how to resolve one issue:
remap the reference, remove it, or link it to a newly created entity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, MutableMapping, MutableSequence

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
            return ReferenceActionResult.error("Impossible de remapper : cible invalide.")

        target_type = _extract_target_type(target)
        updated = _replace_reference_value(reference, target_identifier, target_type)
        if not updated:
            return ReferenceActionResult.error(
                "Impossible de remapper : référence introuvable ou non modifiable."
            )

        return ReferenceActionResult.ok(
            f"Référence remappée vers « {target_identifier} ».",
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
                "Impossible de supprimer : référence introuvable ou non modifiable."
            )

        return ReferenceActionResult.ok(
            f"Référence « {reference.reference_value} » supprimée.",
            _format_reference_change(ReferenceFixAction.REMOVE, reference),
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
            return ReferenceActionResult.error("Impossible de relier : nouvelle entité invalide.")

        changes: list[str] = []
        if attach_to_source and isinstance(new_entity, MutableMapping):
            attach_change = _attach_child_entity(reference, new_entity)
            if attach_change:
                changes.append(attach_change)

        target_type = _extract_target_type(new_entity) or reference.expected_type
        updated = _replace_reference_value(reference, target_identifier, target_type)
        if not updated:
            return ReferenceActionResult.error(
                "Impossible de relier : référence introuvable ou non modifiable."
            )

        changes.append(
            _format_reference_change(
                ReferenceFixAction.LINK_CREATED,
                reference,
                target_identifier,
            )
        )
        return ReferenceActionResult.ok(
            f"Nouvelle entité « {target_identifier} » reliée.",
            *changes,
        )


_IDENTIFIER_KEYS = ("id", "uuid", "slug", "key", "Id", "ID", "Uuid", "Slug", "Key")
_NAME_KEYS = ("name", "Name", "title", "Title", "label", "Label")
_REFERENCE_KEYS = _IDENTIFIER_KEYS + _NAME_KEYS + ("ref", "reference", "target")
_TYPE_KEYS = ("entity_type", "type", "kind", "category", "EntityType", "Type")
_CHILD_COLLECTION_BY_TYPE = {
    "arc": "arcs",
    "scenario": "scenarios",
    "location": "locations",
    "encounter": "encounters",
    "npc": "npcs",
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
    index = _reference_index(reference)
    if _is_mutable_reference_collection(raw_value):
        if index is None or not 0 <= index < len(raw_value):
            return False
        raw_value[index] = _updated_reference_object(
            raw_value[index],
            target_identifier,
            target_type,
        )
        return True

    source_node[reference.field_name] = _updated_reference_object(
        raw_value,
        target_identifier,
        target_type,
    )
    return True


def _remove_reference_value(reference: ReferenceRecord) -> bool:
    source_node = reference.source.node
    if not isinstance(source_node, MutableMapping) or reference.field_name not in source_node:
        return False

    raw_value = source_node[reference.field_name]
    index = _reference_index(reference)
    if _is_mutable_reference_collection(raw_value):
        if index is None or not 0 <= index < len(raw_value):
            return False
        del raw_value[index]
        return True

    del source_node[reference.field_name]
    return True


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

    collection_name = _CHILD_COLLECTION_BY_TYPE.get(
        reference.expected_type,
        f"{reference.expected_type}s",
    )
    collection = source_node.setdefault(collection_name, [])
    if not isinstance(collection, MutableSequence):
        return ""
    if any(item is new_entity for item in collection):
        return ""

    collection.append(new_entity)
    return f"{collection_name}: entité ajoutée"


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
        return f"{location}: référence supprimée"
    return f"{location}: {reference.reference_value} → {target_identifier}"


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
