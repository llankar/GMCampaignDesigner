"""Visual flow planner components and adapters for scenario scenes."""

from __future__ import annotations

import copy
import re
import tkinter as tk
from typing import Any

import customtkinter as ctk
from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import canonicalise_scene

_VISUAL_FLOW_VERSION = 1
_NODE_KNOWN_KEYS = {
    "id",
    "title",
    "scene_index",
    "x",
    "y",
    "kind",
    "summary",
    "_extra_fields",
}
_LINK_KNOWN_KEYS = {"id", "source", "target", "label", "kind", "_extra_fields"}
_SCENE_RECOGNISED_KEYS = {"Title", "Summary", "SceneType", "NextScenes", "LinkData", "_extra_fields"}
_SCENE_TYPE_OVERRIDES = {}


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return base or "scene"


def normalise_flow_node_id(title, existing_ids):
    """Build a stable unique node id from a title and existing ids."""
    used = {str(value).strip() for value in (existing_ids or []) if str(value).strip()}
    base = _slugify(str(title or "Scene"))
    candidate = base
    idx = 2
    while candidate in used:
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate


def normalise_flow_links(nodes, links):
    """Normalise links to existing nodes and keep stable ids."""
    node_ids = {str(node.get("id") or "").strip() for node in (nodes or []) if isinstance(node, dict)}
    out = []
    used_ids = set()
    for link in links or []:
        if not isinstance(link, dict):
            continue
        source = str(link.get("source") or "").strip()
        target = str(link.get("target") or "").strip()
        if source not in node_ids or target not in node_ids:
            continue
        record = {
            "id": str(link.get("id") or "").strip(),
            "source": source,
            "target": target,
            "label": str(link.get("label") or "").strip(),
            "kind": str(link.get("kind") or "scene_link").strip() or "scene_link",
        }
        if not record["id"]:
            record["id"] = normalise_flow_node_id(f"{source}-{target}", used_ids)
        if record["id"] in used_ids:
            record["id"] = normalise_flow_node_id(record["id"], used_ids)
        used_ids.add(record["id"])
        record["_extra_fields"] = {k: copy.deepcopy(v) for k, v in link.items() if k not in _LINK_KNOWN_KEYS}
        out.append(record)
    return out


def _link_targets(scene):
    links = []
    for link in scene.get("LinkData") or []:
        if isinstance(link, dict):
            target = str(link.get("target") or "").strip()
            if target:
                links.append(target)
    if links:
        return links
    return [str(target).strip() for target in (scene.get("NextScenes") or []) if str(target).strip()]


def _build_layered_positions(nodes, scenes):
    title_to_index = {str(scene.get("Title") or ""): idx for idx, scene in enumerate(scenes)}
    edges = {idx: [] for idx in range(len(scenes))}
    indegree = {idx: 0 for idx in range(len(scenes))}
    for idx, scene in enumerate(scenes):
        for target_title in _link_targets(scene):
            target_idx = title_to_index.get(target_title)
            if target_idx is None:
                continue
            edges[idx].append(target_idx)
            indegree[target_idx] += 1

    queue = [idx for idx, degree in indegree.items() if degree == 0]
    layer = {idx: 0 for idx in queue}
    while queue:
        source = queue.pop(0)
        source_layer = layer.get(source, 0)
        for target in edges.get(source, []):
            layer[target] = max(layer.get(target, 0), source_layer + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    for idx in range(len(scenes)):
        layer.setdefault(idx, 0)
    max_layer = max(layer.values()) if layer else 0
    horizontal = max_layer > 0
    grouped = {}
    for idx, depth in layer.items():
        grouped.setdefault(depth, []).append(idx)

    positions = {}
    for depth, members in sorted(grouped.items()):
        for row, idx in enumerate(sorted(members)):
            if horizontal:
                x = 140 + depth * 280
                y = 120 + row * 170
            else:
                x = 140 + row * 260
                y = 120 + depth * 180
            positions[idx] = {"x": x, "y": y}
    for idx, node in enumerate(nodes):
        positions.setdefault(idx, {"x": 120 + (idx % 4) * 260, "y": 120 + (idx // 4) * 180})
        node["x"] = int(positions[idx]["x"])
        node["y"] = int(positions[idx]["y"])


def build_visual_flow_from_scenes(scenes, existing_visual_payload=None):
    """Create deterministic visual flow payload from scenes and optional old payload."""
    scenes_list = [canonicalise_scene(scene if isinstance(scene, dict) else {"Title": str(scene)}, index=i) for i, scene in enumerate(scenes or [])]
    old_payload = existing_visual_payload if isinstance(existing_visual_payload, dict) else {}
    old_nodes = [node for node in (old_payload.get("nodes") or []) if isinstance(node, dict)]
    old_nodes_by_index = {int(node.get("scene_index")): node for node in old_nodes if isinstance(node.get("scene_index"), int)}
    old_nodes_by_id = {str(node.get("id") or "").strip(): node for node in old_nodes if str(node.get("id") or "").strip()}
    old_nodes_by_title = {str(node.get("title") or "").strip().lower(): node for node in old_nodes if str(node.get("title") or "").strip()}

    nodes = []
    used_ids = set()
    for idx, scene in enumerate(scenes_list):
        title = str(scene.get("Title") or f"Scene {idx + 1}").strip()
        previous = old_nodes_by_index.get(idx, {})
        reference_id = str(scene.get("_extra_fields", {}).get("id") or "").strip()
        matched = old_nodes_by_id.get(reference_id) or old_nodes_by_title.get(title.lower()) or previous
        node_id = str(matched.get("id") or "").strip() or normalise_flow_node_id(title, used_ids)
        if node_id in used_ids:
            node_id = normalise_flow_node_id(node_id, used_ids)
        used_ids.add(node_id)
        canvas = scene.get("_canvas") if isinstance(scene.get("_canvas"), dict) else {}
        nodes.append(
            {
                "id": node_id,
                "title": title,
                "scene_index": idx,
                "x": int(canvas.get("x", matched.get("x", 0) or 0)),
                "y": int(canvas.get("y", matched.get("y", 0) or 0)),
                "kind": str(matched.get("kind") or _SCENE_TYPE_OVERRIDES.get(str(scene.get("SceneType") or "").strip(), "scene")).strip() or "scene",
                "summary": str(scene.get("Summary") or ""),
                "scene_fields": {
                    "SceneType": str(scene.get("SceneType") or ""),
                    "structured": {k: copy.deepcopy(v) for k, v in scene.items() if k not in _SCENE_RECOGNISED_KEYS and k != "_extra_fields"},
                    "entities": copy.deepcopy(scene.get("_extra_fields") or {}),
                },
                "_extra_fields": {k: copy.deepcopy(v) for k, v in matched.items() if k not in _NODE_KNOWN_KEYS},
            }
        )
    if any(int(node.get("x", 0)) == 0 and int(node.get("y", 0)) == 0 for node in nodes):
        auto_nodes = [{"id": n["id"], "x": n["x"], "y": n["y"]} for n in nodes]
        _build_layered_positions(auto_nodes, scenes_list)
        for idx, node in enumerate(nodes):
            if int(node.get("x", 0)) == 0 and int(node.get("y", 0)) == 0:
                node["x"] = auto_nodes[idx]["x"]
                node["y"] = auto_nodes[idx]["y"]

    node_by_title = {node["title"]: node["id"] for node in nodes}
    links = []
    for node in nodes:
        source_scene = scenes_list[node["scene_index"]]
        for nxt in _link_targets(source_scene):
            target_id = node_by_title.get(str(nxt or "").strip())
            if target_id:
                links.append({"source": node["id"], "target": target_id, "label": "", "kind": "scene_link"})
    links = normalise_flow_links(nodes, links)
    return {"version": _VISUAL_FLOW_VERSION, "nodes": nodes, "links": links}


def export_visual_flow_to_scenes(flow_payload, existing_scenes=None):
    """Project flow payload back to scenes while preserving unknown fields."""
    existing = [copy.deepcopy(s) if isinstance(s, dict) else {"Title": str(s)} for s in (existing_scenes or [])]
    payload = flow_payload if isinstance(flow_payload, dict) else {}
    nodes = [node for node in (payload.get("nodes") or []) if isinstance(node, dict)]
    links = normalise_flow_links(nodes, payload.get("links") or [])

    scene_map = {idx: scene for idx, scene in enumerate(existing)}
    result = []
    for node in sorted(nodes, key=lambda n: int(n.get("scene_index", 0))):
        idx = int(node.get("scene_index", 0))
        scene = copy.deepcopy(scene_map.get(idx, {}))
        scene.setdefault("_extra_fields", {})
        scene["Title"] = str(node.get("title") or scene.get("Title") or f"Scene {idx + 1}")
        scene["Summary"] = str(scene.get("Summary") or "")
        scene["SceneType"] = str(scene.get("SceneType") or "")
        scene.setdefault("LinkData", scene.get("LinkData") or [])
        scene["_canvas"] = {"x": int(node.get("x", 0)), "y": int(node.get("y", 0))}
        scene_fields = node.get("scene_fields") if isinstance(node.get("scene_fields"), dict) else {}
        for key, value in (scene_fields.get("structured") or {}).items():
            scene[key] = copy.deepcopy(value)
        if scene_fields.get("SceneType"):
            scene["SceneType"] = str(scene_fields.get("SceneType"))
        result.append(scene)

    id_to_title = {str(node.get("id")): str(node.get("title") or "") for node in nodes}
    outgoing = {}
    for link in links:
        outgoing.setdefault(link["source"], []).append(id_to_title.get(link["target"], ""))
    for node in nodes:
        idx = int(node.get("scene_index", 0))
        if idx < len(result):
            result[idx]["NextScenes"] = [title for title in outgoing.get(str(node.get("id")), []) if title]
            for key in _SCENE_RECOGNISED_KEYS:
                result[idx].setdefault(key, [] if key in {"NextScenes", "LinkData"} else "")
    return result


class FlowHierarchyPanel(ctk.CTkFrame):
    def __init__(self, master, on_select=None):
        super().__init__(master)
        self.on_select = on_select
        self._list = tk.Listbox(self, exportselection=False)
        self._list.pack(fill="both", expand=True, padx=8, pady=8)
        self._list.bind("<<ListboxSelect>>", self._emit_select)

    def render(self, nodes):
        self._list.delete(0, "end")
        for node in nodes or []:
            self._list.insert("end", node.get("title") or "Untitled")

    def _emit_select(self, *_):
        selection = self._list.curselection()
        if self.on_select:
            self.on_select(selection[0] if selection else None)


class VisualFlowCanvas(ctk.CTkFrame):
    def __init__(self, master, on_select=None):
        super().__init__(master)
        self.on_select = on_select
        self.canvas = tk.Canvas(self, bg="#0f172a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def render(self, payload):
        self.canvas.delete("all")
        for node in payload.get("nodes") or []:
            x, y = int(node.get("x", 0)), int(node.get("y", 0))
            self.canvas.create_rectangle(x, y, x + 180, y + 80, fill="#1e293b", outline="#64748b")
            self.canvas.create_text(x + 8, y + 8, text=node.get("title") or "Untitled", anchor="nw", fill="#f8fafc")


class FlowPropertiesPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.title_var = ctk.StringVar(value="")
        ctk.CTkLabel(self, text="Properties").pack(anchor="w", padx=8, pady=(8, 4))
        ctk.CTkEntry(self, textvariable=self.title_var).pack(fill="x", padx=8, pady=(0, 8))


class ComponentLibraryPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.search_var = ctk.StringVar(value="")
        ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search components").pack(fill="x", padx=8, pady=8)
        self.palette = ctk.CTkTextbox(self, height=200)
        self.palette.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.palette.insert("1.0", "Scenes\nChoices\nChecks\nCombat\nClues")


class VisualFlowPlanner(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._dirty = False
        self._scenario_title = ""
        self._flow_payload = {"version": _VISUAL_FLOW_VERSION, "nodes": [], "links": []}
        self._scenes = []

        self.hierarchy = FlowHierarchyPanel(self, on_select=self._on_select)
        self.hierarchy.grid(row=0, column=0, sticky="nsew")
        self.canvas = VisualFlowCanvas(self, on_select=self._on_select)
        self.canvas.grid(row=0, column=1, sticky="nsew")
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=2, sticky="nsew")
        self.properties = FlowPropertiesPanel(right)
        self.properties.pack(fill="x")
        self.library = ComponentLibraryPanel(right)
        self.library.pack(fill="both", expand=True)

    def load_from_state(self, scenes, visual_payload=None, scenario_title=""):
        self._scenario_title = str(scenario_title or "")
        self._scenes = [copy.deepcopy(scene) for scene in (scenes or [])]
        self._flow_payload = build_visual_flow_from_scenes(self._scenes, existing_visual_payload=visual_payload)
        self.hierarchy.render(self._flow_payload.get("nodes") or [])
        self.canvas.render(self._flow_payload)
        self._dirty = False

    def export_visual_payload(self):
        return copy.deepcopy(self._flow_payload)

    def export_scenes(self):
        return export_visual_flow_to_scenes(self._flow_payload, existing_scenes=self._scenes)

    def delete_selected(self):
        self.mark_dirty()

    def duplicate_selected(self):
        self.mark_dirty()

    def mark_dirty(self):
        self._dirty = True

    def _on_select(self, _index):
        return
