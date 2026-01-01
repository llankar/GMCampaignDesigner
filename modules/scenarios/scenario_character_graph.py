import copy
import json
import os
import uuid
from tkinter import messagebox

import customtkinter as ctk

from modules.characters.character_graph_editor import (
    CharacterGraphEditor,
    DEFAULT_CHARACTER_GRAPH_PATH,
)
from modules.characters.graph_tabs.importer import merge_graph_into
from modules.characters.graph_tabs.model import ensure_graph_tabs, get_active_tab
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception
from modules.helpers.template_loader import load_template


class ScenarioCharacterGraphEditor(CharacterGraphEditor):
    def __init__(
        self,
        master,
        npc_wrapper,
        pc_wrapper,
        faction_wrapper,
        graph_data=None,
        *args,
        **kwargs,
    ):
        graph_path = _build_temporary_graph_path()
        super().__init__(
            master,
            npc_wrapper=npc_wrapper,
            pc_wrapper=pc_wrapper,
            faction_wrapper=faction_wrapper,
            allowed_entity_types=("npc", "pc"),
            graph_path=graph_path,
            *args,
            **kwargs,
        )
        self.load_graph_data(graph_data or {})

    def init_toolbar(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)

        button_kwargs = {"width": 1}

        ctk.CTkButton(
            toolbar,
            text="Add NPC",
            command=lambda: self.add_entity("npc"),
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Add PC",
            command=lambda: self.add_entity("pc"),
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="New NPC",
            command=lambda: self.create_new_entity("npc"),
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="New PC",
            command=lambda: self.create_new_entity("pc"),
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Add Link",
            command=self.start_link_creation,
            **button_kwargs,
        ).pack(side="left", padx=5)

    def _autosave_graph(self):
        return

    def save_graph(self, path=None, show_message=True):
        return

    def _persist_link_to_entities(self, link):
        return

    def _remove_link_from_entities(self, link):
        return

    def _rebuild_links_from_entities(self):
        return

    def create_new_entity(self, entity_type):  # pragma: no cover - UI interaction
        wrapper = self.entity_wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", "This entity type is not available.")
            return

        template_key = "npcs" if entity_type == "npc" else "pcs"
        try:
            template = load_template(template_key)
        except Exception as exc:
            log_exception(f"Failed to load template for {entity_type}: {exc}")
            messagebox.showerror("Template Error", "Unable to load the template.")
            return

        new_item = {}
        editor = GenericEditorWindow(
            self.winfo_toplevel(),
            new_item,
            template,
            wrapper,
            creation_mode=True,
        )
        self.wait_window(editor)

        if not getattr(editor, "saved", False):
            return

        try:
            wrapper.save_item(new_item)
        except Exception as exc:
            log_exception(f"Failed to save new {entity_type}: {exc}")
            messagebox.showerror("Save Error", "Unable to save the new entry.")
            return

        name_value = new_item.get("Name") or new_item.get("Title")
        if not name_value:
            messagebox.showwarning(
                "Missing Name",
                "The new entry was saved without a name and cannot be placed automatically.",
            )
            return

        if not new_item.get("Name"):
            new_item["Name"] = name_value

        self._refresh_entity_records(entity_type)
        self.pending_entity = {"type": entity_type, "record": new_item}
        self.canvas.bind("<Button-1>", self.place_pending_entity)

    def load_graph_data(self, graph_data):
        for item in self.canvas.find_all():
            if "background" not in self.canvas.gettags(item):
                self.canvas.delete(item)

        self.node_positions.clear()
        self.node_bboxes.clear()
        self.node_images.clear()
        self.node_holder_images.clear()
        self.link_canvas_ids.clear()
        self.shapes.clear()

        graph = copy.deepcopy(graph_data) if isinstance(graph_data, dict) else {}
        graph.setdefault("nodes", [])
        graph.setdefault("links", [])
        graph.setdefault("shapes", [])
        ensure_graph_tabs(graph)
        self.graph = graph

        seen = set()
        for node in self.graph["nodes"]:
            if not isinstance(node, dict):
                continue
            if "entity_type" not in node or "entity_name" not in node:
                if "npc_name" in node:
                    node["entity_type"] = "npc"
                    node["entity_name"] = node.pop("npc_name")
                elif "pc_name" in node:
                    node["entity_type"] = "pc"
                    node["entity_name"] = node.pop("pc_name")
            entity_type = node.get("entity_type", "npc")
            entity_name = node.get("entity_name", "")
            base = f"{entity_type}_{entity_name.replace(' ', '_')}"
            tag = node.get("tag", base)
            if tag in seen:
                index = 1
                while f"{base}_{index}" in seen:
                    index += 1
                tag = f"{base}_{index}"
            node["tag"] = tag
            seen.add(tag)
            node.setdefault("x", 200)
            node.setdefault("y", 200)
            node.setdefault("color", "#1D3572")
            node.setdefault("collapsed", True)

        self.node_positions = {
            node["tag"]: (node.get("x", 200), node.get("y", 200))
            for node in self.graph["nodes"]
            if isinstance(node, dict) and node.get("tag")
        }

        for link in self.graph.get("links", []):
            if not isinstance(link, dict):
                continue
            if "node1_tag" not in link or "node2_tag" not in link:
                if "npc_name1" in link and "npc_name2" in link:
                    link["node1_tag"] = f"npc_{link['npc_name1'].replace(' ', '_')}"
                    link["node2_tag"] = f"npc_{link['npc_name2'].replace(' ', '_')}"
                    link.pop("npc_name1", None)
                    link.pop("npc_name2", None)
                elif "pc_name1" in link and "pc_name2" in link:
                    link["node1_tag"] = f"pc_{link['pc_name1'].replace(' ', '_')}"
                    link["node2_tag"] = f"pc_{link['pc_name2'].replace(' ', '_')}"
                    link.pop("pc_name1", None)
                    link.pop("pc_name2", None)
            link.setdefault("arrow_mode", "both")

        if self.graph["nodes"]:
            self.nodes_collapsed = all(node.get("collapsed", True) for node in self.graph["nodes"])
        else:
            self.nodes_collapsed = True

        shapes_sorted = sorted(self.graph.get("shapes", []), key=lambda s: s.get("z", 0))
        self.shapes = {shape.get("tag"): shape for shape in shapes_sorted if shape.get("tag")}

        max_index = 0
        for shape in self.graph.get("shapes", []):
            tag = shape.get("tag", "")
            if tag.startswith("shape_") and tag.split("_")[-1].isdigit():
                max_index = max(max_index, int(tag.split("_")[-1]))
        self.shape_counter = max_index + 1

        self.original_positions = dict(self.node_positions)
        self.original_shape_positions = {
            shape.get("tag"): (shape.get("x", 0), shape.get("y", 0))
            for shape in self.graph.get("shapes", [])
            if shape.get("tag")
        }

        self._refresh_entity_records("npc")
        self._refresh_entity_records("pc")
        self.draw_graph()

    def export_graph_data(self):
        export_graph = copy.deepcopy(self.graph)
        export_graph.setdefault("nodes", [])
        export_graph.setdefault("links", [])
        export_graph.setdefault("shapes", [])
        ensure_graph_tabs(export_graph)

        for node in export_graph["nodes"]:
            if not isinstance(node, dict):
                continue
            tag = node.get("tag")
            if not tag:
                entity_type = node.get("entity_type", "npc")
                entity_name = node.get("entity_name", "")
                tag = f"{entity_type}_{entity_name.replace(' ', '_')}"
                node["tag"] = tag
            pos = self.node_positions.get(tag)
            if pos:
                node["x"], node["y"] = pos
        for link in export_graph.get("links", []):
            if isinstance(link, dict):
                link.setdefault("arrow_mode", "both")
        for shape in export_graph.get("shapes", []):
            if isinstance(shape, dict):
                shape.pop("canvas_id", None)
                shape.pop("resize_handle", None)

        return export_graph


def sync_scenario_graph_to_global(scenario_graph, graph_path=DEFAULT_CHARACTER_GRAPH_PATH):
    if not isinstance(scenario_graph, dict):
        return False
    if not scenario_graph.get("nodes"):
        return False

    base_graph = {"nodes": [], "links": [], "shapes": []}
    if graph_path and os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as file:
            base_graph = json.load(file)

    ensure_graph_tabs(base_graph)
    shape_counter = _infer_shape_counter(base_graph)
    merge_result = merge_graph_into(base_graph, scenario_graph, nodes_collapsed=True, shape_counter=shape_counter)

    base_graph.setdefault("nodes", []).extend(merge_result.imported_nodes)
    base_graph.setdefault("links", []).extend(_dedupe_links(base_graph, merge_result.imported_links))
    base_graph.setdefault("shapes", []).extend(merge_result.imported_shapes)
    _add_nodes_to_active_tab(base_graph, merge_result.imported_node_tags)

    ensure_graph_tabs(base_graph)
    os.makedirs(os.path.dirname(graph_path), exist_ok=True)
    with open(graph_path, "w", encoding="utf-8") as file:
        json.dump(base_graph, file, ensure_ascii=False, indent=2)
    return True


def _build_temporary_graph_path():
    campaign_dir = ConfigHelper.get_campaign_dir() or os.getcwd()
    graph_dir = os.path.join(campaign_dir, "graphs")
    os.makedirs(graph_dir, exist_ok=True)
    return os.path.join(graph_dir, f"scenario_graph_{uuid.uuid4().hex}.json")


def _infer_shape_counter(graph):
    max_index = 0
    for shape in graph.get("shapes", []):
        if not isinstance(shape, dict):
            continue
        tag = shape.get("tag", "")
        if tag.startswith("shape_") and tag.split("_")[-1].isdigit():
            max_index = max(max_index, int(tag.split("_")[-1]))
    return max_index + 1


def _dedupe_links(base_graph, incoming_links):
    existing = set()
    for link in base_graph.get("links", []):
        if not isinstance(link, dict):
            continue
        existing.add(_link_key(link))

    merged = []
    for link in incoming_links or []:
        if not isinstance(link, dict):
            continue
        key = _link_key(link)
        if key in existing:
            continue
        existing.add(key)
        merged.append(link)
    return merged


def _link_key(link):
    return (
        link.get("node1_tag"),
        link.get("node2_tag"),
        link.get("text") or "",
        link.get("arrow_mode") or "both",
    )


def _add_nodes_to_active_tab(graph, node_tags):
    if not node_tags:
        return
    active_tab = get_active_tab(graph)
    subset = active_tab.get("subsetDefinition") or {}
    if subset.get("mode") == "all":
        return
    existing_tags = set(subset.get("node_tags") or [])
    existing_tags.update(node_tags)
    subset["mode"] = "subset"
    subset["node_tags"] = list(existing_tags)
    active_tab["subsetDefinition"] = subset
