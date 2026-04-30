"""Visual flow planner components and adapters for scenario scenes."""

from __future__ import annotations

import copy
import re
import tkinter as tk
from typing import Any

try:
    from tkinter import ttk
except Exception:  # pragma: no cover - test stubs may not expose ttk
    ttk = None

import customtkinter as ctk
from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import canonicalise_scene, normalise_scene_links
from modules.scenarios.wizard_steps.scenes.scene_entity_fields import normalise_entity_list
from modules.scenarios.scene_structured_fields import compose_scene_text_from_fields, normalise_structured_scene_items
from modules.scenarios.wizard_steps.scenes.flow_canvas.view import VisualFlowCanvas
from modules.scenarios.wizard_steps.scenes.component_library.definitions import COMPONENT_GROUPS
from modules.scenarios.wizard_steps.scenes.flow_properties_panel_helpers import (
    LINK_KIND_VALUES,
    NODE_KIND_VALUES,
    SCENE_ENTITY_FIELDS,
    SCENE_STRUCTURED_FIELDS,
    multiline_from_value,
    string_list_from_multiline,
)

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
_PLAYABLE_NODE_KIND_TO_SCENE_TYPE = {
    "scene": "Scene",
    "objective": "Objective",
    "side_objective": "Side Objective",
    "interaction": "Interaction",
    "condition": "Condition",
    "action": "Action",
    "note": "Note",
}


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
    nodes = [
        node for node in (payload.get("nodes") or [])
        if isinstance(node, dict) and str(node.get("kind") or "scene").strip() in _PLAYABLE_NODE_KIND_TO_SCENE_TYPE
    ]
    links = normalise_flow_links(nodes, payload.get("links") or [])
    existing_by_index = {idx: scene for idx, scene in enumerate(existing)}
    existing_by_title = {
        str(scene.get("Title") or "").strip().casefold(): scene
        for scene in existing
        if str(scene.get("Title") or "").strip()
    }
    result = []
    for node in sorted(nodes, key=lambda n: int(n.get("scene_index", 0))):
        idx = int(node.get("scene_index", 0))
        title = str(node.get("title") or "").strip() or f"Scene {idx + 1}"
        scene = copy.deepcopy(existing_by_index.get(idx) or existing_by_title.get(title.casefold()) or {})
        scene.setdefault("_extra_fields", {})
        scene["Title"] = title
        scene["Summary"] = str(node.get("summary") or scene.get("Summary") or "")
        scene_type = _PLAYABLE_NODE_KIND_TO_SCENE_TYPE.get(str(node.get("kind") or "").strip(), "")
        scene["SceneType"] = scene_type or str(scene.get("SceneType") or "")
        scene["Type"] = scene_type or str(scene.get("Type") or scene.get("SceneType") or "")
        scene.setdefault("LinkData", [])
        scene.setdefault("NextScenes", [])
        scene["_canvas"] = {"x": int(node.get("x", 0)), "y": int(node.get("y", 0))}
        scene_fields = node.get("scene_fields") if isinstance(node.get("scene_fields"), dict) else {}
        for key, value in (scene_fields.get("structured") or {}).items():
            scene[key] = copy.deepcopy(value)
        for key in SCENE_ENTITY_FIELDS:
            scene[key] = normalise_entity_list(scene.get(key))
        for key in SCENE_STRUCTURED_FIELDS:
            scene[key] = normalise_structured_scene_items(scene.get(key))
        if scene_fields.get("SceneType"):
            scene["SceneType"] = str(scene_fields.get("SceneType"))
            scene["Type"] = str(scene_fields.get("SceneType"))
        scene["Text"] = compose_scene_text_from_fields(scene)
        result.append(scene)

    id_to_title = {str(node.get("id")): str(node.get("title") or "") for node in nodes}
    outgoing = {}
    for link in links:
        source_id = str(link["source"])
        target_title = id_to_title.get(link["target"], "")
        if not target_title:
            continue
        outgoing.setdefault(source_id, []).append({"target": target_title, "text": str(link.get("label") or target_title)})
    for index, node in enumerate(sorted(nodes, key=lambda n: int(n.get("scene_index", 0)))):
        if index >= len(result):
            continue
        scene = result[index]
        scene["LinkData"] = outgoing.get(str(node.get("id")), [])
        normalised_links = normalise_scene_links(scene)
        scene["LinkData"] = normalised_links
        scene["NextScenes"] = [link["target"] for link in normalised_links]
        for key in _SCENE_RECOGNISED_KEYS:
            scene.setdefault(key, [] if key in {"NextScenes", "LinkData"} else "")
        scene["Text"] = compose_scene_text_from_fields(scene)
    return result


class FlowHierarchyPanel(ctk.CTkFrame):
    _KIND_PREFIX = {
        "objective": "🟩 ",
        "side_objective": "🔵 ",
        "interaction": "🟨 ",
        "condition": "🟪 ",
        "action": "🟥 ",
        "note": "📝 ",
        "scene": "🎬 ",
    }

    def __init__(self, master, on_select=None, on_open=None):
        super().__init__(master)
        self.on_select = on_select
        self.on_open = on_open
        self._item_to_node_id = {}
        self._node_id_to_item = {}
        self._suspend_events = False
        self._tree = None

        if ttk and hasattr(ttk, "Treeview"):
            self._tree = ttk.Treeview(self, show="tree", selectmode="browse")
            self._tree.pack(fill="both", expand=True, padx=8, pady=8)
            self._tree.bind("<<TreeviewSelect>>", self._emit_select)
            self._tree.bind("<Double-1>", self._emit_open)

    def render(self, nodes, links=None, scenario_title=""):
        if not self._tree:
            return
        self._item_to_node_id.clear()
        self._node_id_to_item.clear()
        self._tree.delete(*self._tree.get_children())

        root_title = str(scenario_title or "Scenario")
        root_id = self._tree.insert("", "end", text=f"📚 {root_title}", open=True)

        ordered_nodes = self._order_nodes(nodes or [], links or [])
        for depth, node in ordered_nodes:
            parent = root_id if depth == 0 else self._node_id_to_item.get(str(node.get("_parent_id") or ""), root_id)
            prefix = self._KIND_PREFIX.get(str(node.get("kind") or "scene").strip(), "🎬 ")
            label = f"{prefix}{str(node.get('title') or 'Untitled')}"
            item_id = self._tree.insert(parent, "end", text=label, open=True)
            node_id = str(node.get("id") or "")
            self._item_to_node_id[item_id] = node_id
            if node_id:
                self._node_id_to_item[node_id] = item_id

    def select_node(self, node_id):
        if not self._tree:
            return
        item_id = self._node_id_to_item.get(str(node_id or ""))
        if not item_id:
            return
        self._suspend_events = True
        try:
            self._tree.selection_set(item_id)
            self._tree.focus(item_id)
            self._tree.see(item_id)
        finally:
            self._suspend_events = False

    def _order_nodes(self, nodes, links):
        by_id = {str(node.get("id") or ""): copy.deepcopy(node) for node in nodes if isinstance(node, dict)}
        outgoing = {}
        incoming = {}
        for link in normalise_flow_links(nodes, links):
            source = str(link.get("source") or "")
            target = str(link.get("target") or "")
            if source in by_id and target in by_id:
                outgoing.setdefault(source, []).append(target)
                incoming[target] = incoming.get(target, 0) + 1

        stable_ids = [str(node.get("id") or "") for node in sorted(nodes, key=lambda n: (int(n.get("scene_index", 0)), str(n.get("id") or "")))]
        roots = [nid for nid in stable_ids if nid and incoming.get(nid, 0) == 0] or stable_ids

        ordered = []
        seen = set()

        def walk(node_id, depth):
            if node_id in seen or node_id not in by_id:
                return
            seen.add(node_id)
            node = by_id[node_id]
            ordered.append((depth, node))
            for child in sorted(outgoing.get(node_id, []), key=lambda cid: stable_ids.index(cid) if cid in stable_ids else 10**6):
                if child in by_id:
                    by_id[child]["_parent_id"] = node_id
                walk(child, depth + 1)

        for rid in roots:
            walk(rid, 0)
        for nid in stable_ids:
            if nid not in seen:
                walk(nid, 0)
        return ordered

    def _emit_select(self, *_):
        if self._suspend_events or not self._tree:
            return
        selection = self._tree.selection()
        node_id = self._item_to_node_id.get(selection[0]) if selection else None
        if self.on_select:
            self.on_select(node_id, source="hierarchy")

    def _emit_open(self, *_):
        if not self._tree:
            return
        selection = self._tree.selection()
        node_id = self._item_to_node_id.get(selection[0]) if selection else None
        if node_id and self.on_open:
            self.on_open(node_id)


class FlowPropertiesPanel(ctk.CTkFrame):
    def __init__(self, master, on_change=None, entity_selector_callbacks=None):
        super().__init__(master)
        self.on_change = on_change
        self.entity_selector_callbacks = entity_selector_callbacks or {}
        self._node = None
        self._link = None
        self._id_edit_enabled = False

        ctk.CTkLabel(self, text="Properties").pack(anchor="w", padx=8, pady=(8, 4))
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._render_empty()

    def bind_item(self, node=None, link=None):
        self._node = node if isinstance(node, dict) else None
        self._link = link if isinstance(link, dict) else None
        self._id_edit_enabled = False
        for child in self._body.winfo_children():
            child.destroy()
        if self._node:
            self._render_node_form(self._node)
        elif self._link:
            self._render_link_form(self._link)
        else:
            self._render_empty()

    def _render_empty(self):
        ctk.CTkLabel(self._body, text="Select a node or link").pack(anchor="w")

    def _render_node_form(self, node):
        self._make_entry("id", str(node.get("id") or ""), readonly=True, key="id")
        ctk.CTkButton(self._body, text="Toggle ID edit", width=110, command=self._toggle_id_edit).pack(anchor="w", pady=(0, 8))
        self._make_entry("title/name", str(node.get("title") or ""), key="title")
        self._make_combo("type", str(node.get("kind") or "scene"), NODE_KIND_VALUES, key="kind")
        self._make_text("summary", multiline_from_value(node.get("summary")), key="summary")
        self._make_checkbox("active", bool(node.get("active", True)), key="active")
        self._make_entry("success condition", str(node.get("success_condition") or ""), key="success_condition")
        self._make_entry("reward/xp", str(node.get("reward_xp") or ""), key="reward_xp")
        self._make_entry("icon", str(node.get("icon") or ""), key="icon")
        scene_fields = node.setdefault("scene_fields", {})
        self._make_entry("SceneType", str(scene_fields.get("SceneType") or ""), key=("scene_fields", "SceneType"))
        structured = scene_fields.setdefault("structured", {})
        for field in SCENE_STRUCTURED_FIELDS:
            self._make_text(field, multiline_from_value(structured.get(field, "")), key=("structured", field))
        entities = scene_fields.setdefault("entities", {})
        for field in SCENE_ENTITY_FIELDS:
            self._make_entity_row(field, multiline_from_value(entities.get(field, [])))

    def _render_link_form(self, link):
        self._make_entry("source", str(link.get("source") or ""), key="source")
        self._make_entry("target", str(link.get("target") or ""), key="target")
        self._make_entry("label", str(link.get("label") or ""), key="label")
        self._make_entry("condition", str(link.get("condition") or ""), key="condition")
        self._make_combo("link type", str(link.get("kind") or "scene_link"), LINK_KIND_VALUES, key="kind")
        ctk.CTkButton(self._body, text="Delete link", fg_color="#7f1d1d", hover_color="#991b1b", command=lambda: self._emit({"_delete": True})).pack(fill="x", pady=(8, 0))

    def _toggle_id_edit(self):
        self._id_edit_enabled = not self._id_edit_enabled
        self.bind_item(self._node, self._link)

    def _make_entry(self, label, value, key=None, readonly=False):
        ctk.CTkLabel(self._body, text=label).pack(anchor="w")
        var = ctk.StringVar(value=str(value or ""))
        state = "normal"
        if readonly and not self._id_edit_enabled:
            state = "disabled"
        entry = ctk.CTkEntry(self._body, textvariable=var, state=state)
        entry.pack(fill="x", pady=(0, 6))
        if key is not None and state == "normal":
            var.trace_add("write", lambda *_a, k=key, v=var: self._emit({k: v.get()}))

    def _make_combo(self, label, value, values, key=None):
        ctk.CTkLabel(self._body, text=label).pack(anchor="w")
        var = ctk.StringVar(value=value if value in values else values[0])
        combo = ctk.CTkComboBox(self._body, values=list(values), variable=var, state="readonly")
        combo.pack(fill="x", pady=(0, 6))
        if key is not None:
            var.trace_add("write", lambda *_a, k=key, v=var: self._emit({k: v.get()}))

    def _make_text(self, label, value, key=None):
        ctk.CTkLabel(self._body, text=label).pack(anchor="w")
        box = ctk.CTkTextbox(self._body, height=62)
        box.pack(fill="x", pady=(0, 6))
        box.insert("1.0", value)
        if key is not None:
            box.bind("<KeyRelease>", lambda _e, k=key, b=box: self._emit({k: b.get("1.0", "end-1c")}), add="+")

    def _make_checkbox(self, label, value, key=None):
        var = ctk.BooleanVar(value=bool(value))
        ctk.CTkCheckBox(self._body, text=label, variable=var, command=lambda k=key, v=var: self._emit({k: bool(v.get())})).pack(anchor="w", pady=(0, 6))

    def _make_entity_row(self, field_name, value):
        ctk.CTkLabel(self._body, text=field_name).pack(anchor="w")
        row = ctk.CTkFrame(self._body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        var = ctk.StringVar(value=value)
        entry = ctk.CTkEntry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        var.trace_add("write", lambda *_a, f=field_name, v=var: self._emit({("entities", f): v.get()}))
        callback = self.entity_selector_callbacks.get(field_name)
        ctk.CTkButton(row, text="Select", width=70, state="normal" if callback else "disabled", command=lambda f=field_name, v=var, cb=callback: self._select_entities(f, v, cb)).pack(side="left", padx=(6, 0))

    def _select_entities(self, field_name, variable, callback):
        if not callable(callback):
            return
        selected = callback(string_list_from_multiline(variable.get()))
        variable.set("\n".join(selected or []))
        self._emit({("entities", field_name): variable.get()})

    def _emit(self, changes):
        if callable(self.on_change):
            self.on_change(changes, node=self._node, link=self._link)


class ComponentLibraryPanel(ctk.CTkFrame):
    def __init__(self, master, on_item_click=None):
        super().__init__(master)
        self.on_item_click = on_item_click
        self.search_var = ctk.StringVar(value="")
        self.search_var.trace_add("write", lambda *_: self._render_items())
        ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search components").pack(fill="x", padx=8, pady=8)
        self._list = ctk.CTkScrollableFrame(self)
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._render_items()

    def _render_items(self):
        for child in self._list.winfo_children():
            child.destroy()
        query = self.search_var.get().strip().lower()
        for group in COMPONENT_GROUPS:
            visible = []
            for item in group.get("items", []):
                text = f"{item.get('label', '')} {item.get('kind', '')}"
                if query and query not in text.lower():
                    continue
                visible.append(item)
            if not visible:
                continue
            ctk.CTkLabel(self._list, text=group.get("name", ""), text_color="#94a3b8").pack(anchor="w", pady=(8, 4))
            for item in visible:
                label = f"{item.get('icon', '•')}  {item.get('label', item.get('kind', ''))}"
                ctk.CTkButton(
                    self._list,
                    text=label,
                    anchor="w",
                    fg_color=item.get("color", "#334155"),
                    hover_color="#1e293b",
                    command=lambda k=item.get("kind"): self._emit_click(k),
                ).pack(fill="x", pady=2)

    def _emit_click(self, kind):
        if callable(self.on_item_click):
            self.on_item_click(kind)


class VisualFlowPlanner(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._dirty = False
        self._scenario_title = ""
        self._flow_payload = {"version": _VISUAL_FLOW_VERSION, "nodes": [], "links": []}
        self._scenes = []

        self.hierarchy = FlowHierarchyPanel(self, on_select=self._on_select, on_open=self._open_node_properties)
        self.hierarchy.grid(row=0, column=0, sticky="nsew")
        self.canvas = VisualFlowCanvas(self, on_select=self._on_select, on_change=self.mark_dirty, on_save=self._safe_save)
        self.canvas.grid(row=0, column=1, sticky="nsew")
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=2, sticky="nsew")
        self.properties = FlowPropertiesPanel(right, on_change=self._on_properties_change, entity_selector_callbacks=getattr(self, "entity_selector_callbacks", None))
        self.properties.pack(fill="x")
        self.library = ComponentLibraryPanel(right, on_item_click=self._create_node_from_library)
        self.library.pack(fill="both", expand=True)


    def _create_node_from_library(self, kind):
        node = self.canvas.create_node_at_viewport_center(kind)
        if node:
            self.mark_dirty()
            self.hierarchy.render(self.canvas.model.payload.get("nodes") or [], self.canvas.model.payload.get("links") or [], self._scenario_title)
            self._on_select(node.get("id"), source="canvas")

    def set_entity_selector_callbacks(self, callbacks):
        self.entity_selector_callbacks = callbacks or {}
        self.properties.entity_selector_callbacks = self.entity_selector_callbacks

    def load_from_state(self, scenes, visual_payload=None, scenario_title=""):
        self._scenario_title = str(scenario_title or "")
        self._scenes = [copy.deepcopy(scene) for scene in (scenes or [])]
        self._flow_payload = build_visual_flow_from_scenes(self._scenes, existing_visual_payload=visual_payload)
        self.hierarchy.render(self._flow_payload.get("nodes") or [], self._flow_payload.get("links") or [], self._scenario_title)
        self.canvas.set_payload(self._flow_payload)
        self._dirty = False

    def export_visual_payload(self):
        self._flow_payload = self.canvas.export_payload()
        return copy.deepcopy(self._flow_payload)

    def export_scenes(self):
        self._flow_payload = self.canvas.export_payload()
        return export_visual_flow_to_scenes(self._flow_payload, existing_scenes=self._scenes)

    def delete_selected(self):
        self.canvas.delete_selected()

    def duplicate_selected(self):
        self.canvas.duplicate_selected()

    def mark_dirty(self):
        self._dirty = True

    def _on_select(self, item_id, source=""):
        payload = self.canvas.model.payload
        node = next((n for n in (payload.get("nodes") or []) if str(n.get("id") or "") == str(item_id or "")), None)
        link = None if node else next((l for l in (payload.get("links") or []) if str(l.get("id") or "") == str(item_id or "")), None)
        if node and source != "hierarchy":
            self.hierarchy.select_node(item_id)
        if node and source != "canvas":
            self.canvas.select_node(item_id, emit=False)
        self.properties.bind_item(node=node, link=link)

    def _open_node_properties(self, node_id):
        self._on_select(node_id, source="hierarchy")

    def _on_properties_change(self, changes, node=None, link=None):
        if not isinstance(changes, dict):
            return
        payload = self.canvas.model.payload
        target = node if isinstance(node, dict) else link
        if not isinstance(target, dict):
            return
        if changes.get("_delete") and link is target:
            self.canvas.model.remove_link(str(link.get("id") or ""))
        else:
            scene_fields = target.setdefault("scene_fields", {}) if target is node else None
            for key, value in changes.items():
                if isinstance(key, tuple) and key and key[0] == "scene_fields" and node is target:
                    scene_fields[key[1]] = str(value or "")
                elif isinstance(key, tuple) and key and key[0] == "structured" and node is target:
                    scene_fields.setdefault("structured", {})[key[1]] = string_list_from_multiline(value)
                elif isinstance(key, tuple) and key and key[0] == "entities" and node is target:
                    scene_fields.setdefault("entities", {})[key[1]] = string_list_from_multiline(value)
                elif key == "summary" and node is target:
                    target[key] = str(value or "")
                elif key == "id" and node is target:
                    new_id = str(value or "").strip()
                    if new_id and new_id != str(target.get("id") or ""):
                        old_id = str(target.get("id") or "")
                        target["id"] = new_id
                        for lk in payload.get("links") or []:
                            if str(lk.get("source") or "") == old_id:
                                lk["source"] = new_id
                            if str(lk.get("target") or "") == old_id:
                                lk["target"] = new_id
                else:
                    target[key] = value
        self.mark_dirty()
        self.hierarchy.render(payload.get("nodes") or [], payload.get("links") or [], self._scenario_title)
        self.canvas.render()

    def _safe_save(self):
        callback = getattr(self, "save_state", None)
        if callable(callback):
            callback()
