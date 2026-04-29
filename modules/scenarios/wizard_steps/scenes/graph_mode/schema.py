"""Typed schema models and deterministic helpers for graph mode planner."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from typing import Any, Mapping

SCENE_DEFAULT_TITLE = "Objective principal"
GRAPH_SCHEMA_VERSION = "1.0"


@dataclass(slots=True, frozen=True)
class GraphNodePosition:
    """Canvas position for a graph node."""

    x: float
    y: float


@dataclass(slots=True, frozen=True)
class GraphNode:
    """Typed graph node model."""

    id: str
    type: str
    title: str
    position: GraphNodePosition
    payload: dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass(slots=True, frozen=True)
class GraphEdge:
    """Typed graph edge model."""

    id: str
    source: str
    target: str
    label: str = ""
    condition_type: str = "always"


@dataclass(slots=True, frozen=True)
class GraphScenarioDocument:
    """Top-level graph scenario document used for import/export."""

    schema_version: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    meta: dict[str, Any] | None = None


def normalize_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = dict(scene or {})
    normalized["title"] = str(normalized.get("title") or f"Scene {index}").strip()
    normalized["objective"] = str(normalized.get("objective") or "").strip()
    normalized["success_condition"] = str(normalized.get("success_condition") or "").strip()
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    return normalized


def deterministic_graph_id(prefix: str, *parts: str) -> str:
    """Create deterministic IDs for import/export stable round-trips."""

    canonical = "|".join(str(part).strip() for part in parts)
    digest = sha1(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def stable_sort_nodes(nodes: list[GraphNode]) -> tuple[GraphNode, ...]:
    """Stable canonical ordering for graph nodes."""

    return tuple(sorted(nodes, key=lambda node: (node.type.casefold(), node.title.casefold(), node.id)))


def stable_sort_edges(edges: list[GraphEdge]) -> tuple[GraphEdge, ...]:
    """Stable canonical ordering for graph edges."""

    return tuple(
        sorted(
            edges,
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.condition_type.casefold(),
                edge.label.casefold(),
                edge.id,
            ),
        )
    )


def build_graph_document(
    *,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    meta: Mapping[str, Any] | None = None,
    schema_version: str = GRAPH_SCHEMA_VERSION,
) -> GraphScenarioDocument:
    """Build a canonical graph scenario document with deterministic ordering."""

    canonical_meta = dict(meta) if meta else None
    return GraphScenarioDocument(
        schema_version=schema_version,
        nodes=stable_sort_nodes(nodes),
        edges=stable_sort_edges(edges),
        meta=canonical_meta,
    )
