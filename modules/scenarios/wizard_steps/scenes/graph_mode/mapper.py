"""Mapping helpers between scene payloads and UI text."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .schema import (
    GRAPH_SCHEMA_VERSION,
    GraphEdge,
    GraphNode,
    GraphNodePosition,
    GraphScenarioDocument,
    build_graph_document,
)


def scenes_to_node_lines(scenes: list[dict]) -> list[str]:
    lines: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        marker = "🎯" if index == 1 else "💬"
        lines.append(f"{marker} {index}. {scene.get('title')}")
        if scene.get("objective"):
            lines.append(f"   └─ objectif: {scene['objective']}")
        if index < len(scenes):
            lines.append(f"   └─ ensuite → {index + 1}")
    return lines


def scenes_to_graph_document(scenes: list[dict]) -> GraphScenarioDocument:
    """Convert wizard scenes payload to a canonical graph document."""

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    id_by_index: list[str] = []

    for index, raw_scene in enumerate(scenes or []):
        scene = dict(raw_scene or {})
        scene_id = str(scene.get("id") or scene.get("Id") or scene.get("SceneId") or f"scene_{index + 1}")
        id_by_index.append(scene_id)
        canvas = scene.get("_canvas") if isinstance(scene.get("_canvas"), dict) else {}
        x = float(canvas.get("x", 220 + (index * 240)))
        y = float(canvas.get("y", 220))
        title = str(scene.get("Title") or scene.get("title") or f"Scene {index + 1}").strip()
        node_type = str(scene.get("SceneType") or scene.get("type") or "scene").strip() or "scene"
        legacy_keys = {
            "id", "Id", "SceneId", "Title", "title", "SceneType", "type", "NextScenes", "_canvas", "_links"
        }
        payload = {k: deepcopy(v) for k, v in scene.items() if k not in legacy_keys}
        nodes.append(
            GraphNode(id=scene_id, type=node_type, title=title, position=GraphNodePosition(x=x, y=y), payload=payload)
        )

    for index, raw_scene in enumerate(scenes or []):
        scene = dict(raw_scene or {})
        source = id_by_index[index]
        next_scenes = scene.get("NextScenes") if isinstance(scene.get("NextScenes"), list) else []
        links = scene.get("_links") if isinstance(scene.get("_links"), list) else []

        if next_scenes:
            for target in next_scenes:
                if not target:
                    continue
                target_id = str(target)
                label = "next"
                match = next((l for l in links if isinstance(l, dict) and str(l.get("target")) == target_id), None)
                if isinstance(match, dict):
                    raw_label = str(match.get("label") or match.get("text") or "").strip().casefold()
                    if raw_label in {"yes", "no", "success", "fail", "next"}:
                        label = raw_label
                edges.append(GraphEdge(id=f"edge_{source}_{target_id}_{label}", source=source, target=target_id, label=label))
        elif index + 1 < len(id_by_index):
            target_id = id_by_index[index + 1]
            edges.append(GraphEdge(id=f"edge_{source}_{target_id}_next", source=source, target=target_id, label="next"))

    return build_graph_document(nodes=nodes, edges=edges, meta={"source": "wizard-scenes"}, schema_version=GRAPH_SCHEMA_VERSION)


def graph_document_to_scenes(doc: GraphScenarioDocument) -> list[dict]:
    """Convert graph document back to wizard scenes payload."""

    nodes = list(doc.nodes or ())
    edges = sorted(doc.edges or (), key=lambda e: (e.source, e.target, (e.label or "").casefold(), e.id))
    edges_by_source: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        edges_by_source.setdefault(edge.source, []).append(edge)

    def _sort_key(item: GraphNode) -> tuple[float, float, str]:
        return (item.position.y, item.position.x, item.id)

    ordered_nodes = sorted(nodes, key=_sort_key)
    scenes: list[dict[str, Any]] = []
    for node in ordered_nodes:
        payload = deepcopy(node.payload) if isinstance(node.payload, dict) else {}
        scene: dict[str, Any] = payload
        scene["id"] = node.id
        scene["Title"] = node.title
        scene["SceneType"] = node.type
        scene["_canvas"] = {"x": node.position.x, "y": node.position.y}

        node_edges = edges_by_source.get(node.id, [])
        if node_edges:
            scene["NextScenes"] = [edge.target for edge in node_edges]
            scene["_links"] = [{"target": edge.target, "label": edge.label or "next"} for edge in node_edges]
        scenes.append(scene)
    return scenes
