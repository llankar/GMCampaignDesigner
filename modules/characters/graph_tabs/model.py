import uuid
from typing import Dict, List, Tuple

DEFAULT_TAB_NAME = "All"
DEFAULT_SUBSET_DEFINITION = {"mode": "all"}


def _new_tab_id() -> str:
    return uuid.uuid4().hex


def build_default_tab() -> Dict:
    return {
        "id": _new_tab_id(),
        "name": DEFAULT_TAB_NAME,
        "subsetDefinition": DEFAULT_SUBSET_DEFINITION.copy(),
        "layoutPrefs": {},
    }


def ensure_graph_tabs(graph: Dict) -> None:
    if not isinstance(graph, dict):
        return
    tabs = graph.get("tabs")
    if not isinstance(tabs, list) or not tabs:
        graph["tabs"] = [build_default_tab()]
    else:
        normalized = []
        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            tab.setdefault("id", _new_tab_id())
            tab.setdefault("name", DEFAULT_TAB_NAME)
            tab.setdefault("subsetDefinition", DEFAULT_SUBSET_DEFINITION.copy())
            tab.setdefault("layoutPrefs", {})
            normalized.append(tab)
        if not normalized:
            normalized = [build_default_tab()]
        graph["tabs"] = normalized

    active_id = graph.get("active_tab_id")
    if not active_id or active_id not in {tab["id"] for tab in graph["tabs"]}:
        graph["active_tab_id"] = graph["tabs"][0]["id"]


def get_active_tab(graph: Dict) -> Dict:
    ensure_graph_tabs(graph)
    active_id = graph.get("active_tab_id")
    return next((tab for tab in graph["tabs"] if tab.get("id") == active_id), graph["tabs"][0])


def set_active_tab(graph: Dict, tab_id: str) -> None:
    ensure_graph_tabs(graph)
    if tab_id in {tab["id"] for tab in graph["tabs"]}:
        graph["active_tab_id"] = tab_id


def filter_graph_for_tab(graph: Dict, tab: Dict) -> Tuple[List[Dict], List[Dict]]:
    nodes = list(graph.get("nodes", []))
    links = list(graph.get("links", []))
    subset = (tab or {}).get("subsetDefinition") or {}
    if subset.get("mode") == "all":
        return nodes, links

    node_tags = set(subset.get("node_tags") or [])
    entity_types = {t for t in subset.get("entity_types") or [] if t}
    search = (subset.get("search") or "").strip().lower()
    if not node_tags and not entity_types and not search:
        return [], []

    filtered_nodes = []
    for node in nodes:
        tag = node.get("tag")
        if node_tags and tag not in node_tags:
            continue
        if entity_types and node.get("entity_type") not in entity_types:
            continue
        if search:
            haystacks = [
                str(node.get("entity_name") or "").lower(),
                str(node.get("name") or "").lower(),
                str(node.get("tag") or "").lower(),
            ]
            if not any(search in hay for hay in haystacks):
                continue
        filtered_nodes.append(node)

    visible_tags = {node.get("tag") for node in filtered_nodes}
    filtered_links = [
        link for link in links
        if link.get("node1_tag") in visible_tags
        and link.get("node2_tag") in visible_tags
    ]
    return filtered_nodes, filtered_links
