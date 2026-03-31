"""Utilities for graph tabs importer."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .model import ensure_graph_tabs


@dataclass
class GraphImportResult:
    imported_nodes: List[Dict]
    imported_links: List[Dict]
    imported_shapes: List[Dict]
    imported_node_tags: List[str]
    shape_counter: int


def merge_graph_into(
    existing_graph: Dict,
    imported_graph: Dict,
    nodes_collapsed: bool,
    shape_counter: int,
) -> GraphImportResult:
    """Merge graph into."""
    if not isinstance(imported_graph, dict):
        raise ValueError("Selected file does not contain a valid graph.")

    imported_nodes = imported_graph.get("nodes") or []
    imported_links = imported_graph.get("links") or []
    imported_shapes = imported_graph.get("shapes") or []
    if not isinstance(imported_nodes, list) or not isinstance(imported_links, list) or not isinstance(imported_shapes, list):
        raise ValueError("Selected file does not contain a valid graph structure.")

    ensure_graph_tabs(existing_graph)
    existing_tags = {node.get("tag") for node in existing_graph.get("nodes", []) if node.get("tag")}
    existing_shape_tags = {shape.get("tag") for shape in existing_graph.get("shapes", []) if shape.get("tag")}
    tag_map = {}
    imported_node_tags: List[str] = []
    imported_entities: Dict[Tuple[str, str], str] = {}
    normalized_nodes: List[Dict] = []

    for node in imported_nodes:
        # Process each node from imported_nodes.
        if not isinstance(node, dict):
            continue
        entity_type, entity_name = _normalize_entity(node)
        base = f"{entity_type}_{entity_name.replace(' ', '_')}"
        original_tag = node.get("tag") or base
        tag = _unique_tag(base, original_tag, existing_tags)
        node["tag"] = tag
        node.setdefault("x", 0)
        node.setdefault("y", 0)
        node.setdefault("color", "#1D3572")
        node.setdefault("collapsed", nodes_collapsed)
        existing_tags.add(tag)
        tag_map[original_tag] = tag
        imported_node_tags.append(tag)
        imported_entities[(entity_type, entity_name)] = tag
        normalized_nodes.append(node)

    normalized_links: List[Dict] = []
    for link in imported_links:
        # Process each link from imported_links.
        if not isinstance(link, dict):
            continue
        node1_tag, node2_tag = _normalize_link_tags(link, imported_entities)
        if node1_tag:
            node1_tag = tag_map.get(node1_tag, node1_tag)
        if node2_tag:
            node2_tag = tag_map.get(node2_tag, node2_tag)
        if not node1_tag or not node2_tag:
            continue
        if node1_tag not in existing_tags or node2_tag not in existing_tags:
            continue
        link["node1_tag"] = node1_tag
        link["node2_tag"] = node2_tag
        link.setdefault("arrow_mode", "both")
        normalized_links.append(link)

    normalized_shapes: List[Dict] = []
    for shape in imported_shapes:
        # Process each shape from imported_shapes.
        if not isinstance(shape, dict):
            continue
        shape.pop("canvas_id", None)
        shape.pop("resize_handle", None)
        tag = shape.get("tag")
        if not tag or tag in existing_shape_tags:
            # Handle the branch where tag is unavailable or tag is in existing shape tags.
            tag = f"shape_{shape_counter}"
            while tag in existing_shape_tags:
                # Keep looping while tag is in existing_shape_tags.
                shape_counter += 1
                tag = f"shape_{shape_counter}"
            shape_counter += 1
        elif tag.startswith("shape_") and tag.split("_")[-1].isdigit():
            shape_counter = max(shape_counter, int(tag.split("_")[-1]) + 1)
        shape["tag"] = tag
        existing_shape_tags.add(tag)
        normalized_shapes.append(shape)

    return GraphImportResult(
        imported_nodes=normalized_nodes,
        imported_links=normalized_links,
        imported_shapes=normalized_shapes,
        imported_node_tags=imported_node_tags,
        shape_counter=shape_counter,
    )


def _normalize_entity(node: Dict) -> Tuple[str, str]:
    """Normalize entity."""
    if "entity_type" not in node or "entity_name" not in node:
        if "npc_name" in node:
            # Handle the branch where 'npc_name' is in node.
            node["entity_type"] = "npc"
            node["entity_name"] = node.pop("npc_name")
        elif "pc_name" in node:
            node["entity_type"] = "pc"
            node["entity_name"] = node.pop("pc_name")
    entity_type = node.get("entity_type", "npc")
    entity_name = node.get("entity_name", "")
    return entity_type, entity_name


def _normalize_link_tags(link: Dict, imported_entities: Dict[Tuple[str, str], str]) -> Tuple[Optional[str], Optional[str]]:
    """Normalize link tags."""
    node1_tag = link.get("node1_tag")
    node2_tag = link.get("node2_tag")
    if not node1_tag or not node2_tag:
        if "npc_name1" in link and "npc_name2" in link:
            # Handle the branch where 'npc_name1' is in link and 'npc_name2' is in link.
            node1_tag = imported_entities.get(("npc", link.get("npc_name1")))
            node2_tag = imported_entities.get(("npc", link.get("npc_name2")))
        elif "pc_name1" in link and "pc_name2" in link:
            node1_tag = imported_entities.get(("pc", link.get("pc_name1")))
            node2_tag = imported_entities.get(("pc", link.get("pc_name2")))
    return node1_tag, node2_tag


def _unique_tag(base: str, original: str, existing_tags) -> str:
    """Internal helper for unique tag."""
    tag = original
    if tag in existing_tags:
        # Handle the branch where tag is in existing tags.
        i = 1
        while f"{base}_{i}" in existing_tags:
            # Keep looping while f'{base}_{i}' is in existing_tags.
            i += 1
        tag = f"{base}_{i}"
    return tag
