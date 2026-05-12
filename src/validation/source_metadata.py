"""Optional source metadata for validation hierarchy projections.

Campaign validation often works on normalized copies of persisted entities.  These
helpers let UI launchers remember which persisted item and field a projected node
came from without changing the public validator models.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

SOURCE_ITEM_KEY = "__validation_source_item__"
SOURCE_WRAPPER_KEY = "__validation_source_wrapper__"
FIELD_ALIASES_KEY = "__validation_field_aliases__"


def attach_source_metadata(
    node: MutableMapping[str, Any],
    *,
    source_item: MutableMapping[str, Any] | None,
    wrapper: Any = None,
    field_aliases: Mapping[str, str] | None = None,
) -> None:
    """Attach persistence metadata to a normalized validation node in-place."""

    if source_item is not None:
        node[SOURCE_ITEM_KEY] = source_item
    if wrapper is not None:
        node[SOURCE_WRAPPER_KEY] = wrapper
    aliases = {key: value for key, value in (field_aliases or {}).items() if key and value}
    if aliases:
        node[FIELD_ALIASES_KEY] = aliases


def source_item_for(node: Mapping[str, Any]) -> MutableMapping[str, Any] | None:
    """Return the persisted item behind ``node``, when metadata is present."""

    source_item = node.get(SOURCE_ITEM_KEY)
    return source_item if isinstance(source_item, MutableMapping) else None


def source_wrapper_for(node: Mapping[str, Any]) -> Any:
    """Return the persistence wrapper behind ``node``, when metadata is present."""

    return node.get(SOURCE_WRAPPER_KEY)


def source_field_for(node: Mapping[str, Any], field_name: str) -> str:
    """Return the persisted field mirrored by a normalized reference field."""

    aliases = node.get(FIELD_ALIASES_KEY)
    if isinstance(aliases, Mapping):
        alias = aliases.get(field_name)
        if isinstance(alias, str) and alias:
            return alias
    return field_name
