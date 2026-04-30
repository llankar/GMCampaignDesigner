"""Undo-friendly command primitives for visual flow changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    changed: bool
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)


def make_delete_node_command(*, node_id: str, removed_node: dict[str, Any] | None, removed_links: list[dict[str, Any]]) -> CommandResult:
    return CommandResult(
        changed=bool(removed_node),
        before={"node": removed_node, "links": list(removed_links)},
        after={"node_id": str(node_id or "")},
    )


def make_update_link_command(*, link_id: str, before: dict[str, Any], after: dict[str, Any]) -> CommandResult:
    return CommandResult(
        changed=before != after,
        before={"link_id": str(link_id or ""), "payload": dict(before or {})},
        after={"link_id": str(link_id or ""), "payload": dict(after or {})},
    )


def make_create_link_command(*, source_id: str, target_id: str, link_payload: dict[str, Any]) -> CommandResult:
    return CommandResult(
        changed=bool(source_id and target_id),
        before={},
        after={"source": str(source_id or ""), "target": str(target_id or ""), "link": dict(link_payload or {})},
    )
