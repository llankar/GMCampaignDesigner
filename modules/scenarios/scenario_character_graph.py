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
from modules.characters.graph_tabs.model import build_default_tab, ensure_graph_tabs
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
        on_entity_added=None,
        on_entity_removed=None,
        node_style=None,
        *args,
        **kwargs,
    ):
        self._on_entity_added = on_entity_added
        self._on_entity_removed = on_entity_removed
        graph_path = _build_temporary_graph_path()
        super().__init__(
            master,
            npc_wrapper=npc_wrapper,
            pc_wrapper=pc_wrapper,
            faction_wrapper=faction_wrapper,
            allowed_entity_types=("npc", "pc"),
            graph_path=graph_path,
            node_style=node_style,
            *args,
            **kwargs,
        )
        self.load_graph_data(graph_data or {})

    def place_pending_entity(self, event):
        entity = self.pending_entity
        if not entity:
            return
        super().place_pending_entity(event)
        if callable(self._on_entity_added):
            name_value = entity.get("record", {}).get("Name")
            if name_value:
                self._on_entity_added(entity.get("type"), name_value)

    def delete_node(self):
        tag = self.selected_node
        entity_info = self._get_node_entity_info(tag) if tag else None
        super().delete_node()
        if not entity_info:
            return
        if any(
            isinstance(node, dict) and node.get("tag") == tag
            for node in self.graph.get("nodes", [])
        ):
            return
        if callable(self._on_entity_removed):
            entity_type, entity_name = entity_info
            self._on_entity_removed(entity_type, entity_name)

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
        ctk.CTkButton(
            toolbar,
            text="+/-",
            command=self.toggle_nodes_collapsed,
            **button_kwargs,
        ).pack(side="left", padx=5)

    def _autosave_graph(self):
        return

    def save_graph(self, path=None, show_message=True):
        return

    def _persist_link_to_entities(self, link):
        super()._persist_link_to_entities(link)

    def _remove_link_from_entities(self, link):
        super()._remove_link_from_entities(link)

    def _rebuild_links_from_entities(self):
        super()._rebuild_links_from_entities()

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
        tag_mapping = {}
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
            original_tag = node.get("tag", base)
            tag = original_tag
            if original_tag in seen:
                index = 1
                while f"{base}_{index}" in seen:
                    index += 1
                tag = f"{base}_{index}"
            node["tag"] = tag
            seen.add(tag)
            tag_mapping[original_tag] = tag
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
            if link.get("node1_tag") in tag_mapping:
                link["node1_tag"] = tag_mapping[link["node1_tag"]]
            if link.get("node2_tag") in tag_mapping:
                link["node2_tag"] = tag_mapping[link["node2_tag"]]
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
        self._merge_links_from_entities()
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

    def _merge_links_from_entities(self):
        tag_lookup = {}
        for node in self.graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            entity_type = node.get("entity_type")
            entity_name = node.get("entity_name")
            tag = node.get("tag")
            if not tag:
                continue
            key = self._normalize_entity_key(entity_type, entity_name)
            if key not in tag_lookup:
                tag_lookup[key] = tag
        if not tag_lookup:
            return False
        existing_links = [link for link in self.graph.get("links", []) if isinstance(link, dict)]
        existing_keys = {
            _entity_link_key(link)
            for link in existing_links
            if link.get("node1_tag") and link.get("node2_tag")
        }
        new_links = []
        for node in self.graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            entity_type = node.get("entity_type")
            entity_name = node.get("entity_name")
            tag = self._find_tag_for_entity(tag_lookup, entity_type, entity_name)
            if not tag:
                continue
            record = self._get_entity_record(entity_type, entity_name)
            if not record:
                continue
            for link in self._normalize_links_list(record):
                if not isinstance(link, dict):
                    continue
                target_type = link.get("target_type")
                target_name = link.get("target_name")
                label = link.get("label") or ""
                target_tag = self._find_tag_for_entity(tag_lookup, target_type, target_name)
                if not target_tag:
                    continue
                link_data = {
                    "node1_tag": tag,
                    "node2_tag": target_tag,
                    "text": label,
                    "arrow_mode": link.get("arrow_mode") or "both",
                }
                link_key = _entity_link_key(link_data)
                if link_key in existing_keys:
                    continue
                existing_keys.add(link_key)
                new_links.append(link_data)
        if new_links:
            self.graph.setdefault("links", []).extend(new_links)
            return True
        return False


def sync_scenario_graph_to_global(
    scenario_graph,
    scenario_name,
    graph_path=DEFAULT_CHARACTER_GRAPH_PATH,
):
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

    scenario_tab = next(
        (tab for tab in base_graph.get("tabs", []) if tab.get("name") == scenario_name),
        None,
    )
    if scenario_tab is None:
        scenario_tab = build_default_tab()
        scenario_tab["name"] = scenario_name
        scenario_tab["subsetDefinition"] = {
            "mode": "subset",
            "node_tags": list(merge_result.imported_node_tags),
        }
        base_graph.setdefault("tabs", []).append(scenario_tab)
    else:
        subset = scenario_tab.get("subsetDefinition") or {}
        existing_tags = set(subset.get("node_tags") or [])
        existing_tags.update(merge_result.imported_node_tags)
        scenario_tab["subsetDefinition"] = {
            "mode": "subset",
            "node_tags": list(existing_tags),
        }
    if scenario_tab.get("id"):
        base_graph["active_tab_id"] = scenario_tab["id"]

    ensure_graph_tabs(base_graph)
    os.makedirs(os.path.dirname(graph_path), exist_ok=True)
    with open(graph_path, "w", encoding="utf-8") as file:
        json.dump(base_graph, file, ensure_ascii=False, indent=2)
    return True


def build_scenario_graph_with_links(
    scenario_graph,
    scenario_npcs,
    scenario_pcs,
    graph_path=DEFAULT_CHARACTER_GRAPH_PATH,
):
    # Scenario graphs are isolated from the global character graph; only scenario data applies.
    base_graph = copy.deepcopy(scenario_graph) if isinstance(scenario_graph, dict) else {}
    base_graph.setdefault("nodes", [])
    base_graph.setdefault("links", [])
    base_graph.setdefault("shapes", [])
    ensure_graph_tabs(base_graph)
    if not base_graph["nodes"]:
        added_nodes = []
        seen_tags = set()
        for entity_type, names in (("npc", scenario_npcs), ("pc", scenario_pcs)):
            for name in names or []:
                if not name:
                    continue
                base = f"{entity_type}_{name.replace(' ', '_')}"
                tag = base
                index = 1
                while tag in seen_tags:
                    tag = f"{base}_{index}"
                    index += 1
                node = {
                    "entity_type": entity_type,
                    "entity_name": name,
                    "tag": tag,
                    "x": 200,
                    "y": 200,
                    "color": "#1D3572",
                    "collapsed": True,
                }
                base_graph["nodes"].append(node)
                added_nodes.append(node)
                seen_tags.add(tag)
        _layout_new_scenario_nodes(base_graph, added_nodes)

    node_tags = {
        node.get("tag") for node in base_graph.get("nodes", []) if isinstance(node, dict)
    }
    filtered_links = []
    for link in base_graph.get("links", []):
        if not isinstance(link, dict):
            continue
        node1_tag, node2_tag = _normalize_link_tags(link)
        if not node1_tag or not node2_tag:
            continue
        if node1_tag not in node_tags or node2_tag not in node_tags:
            continue
        link["node1_tag"] = node1_tag
        link["node2_tag"] = node2_tag
        link.setdefault("arrow_mode", "both")
        filtered_links.append(link)
    base_graph["links"] = filtered_links
    return base_graph


def _build_temporary_graph_path():
    campaign_dir = ConfigHelper.get_campaign_dir() or os.getcwd()
    graph_dir = os.path.join(campaign_dir, "graphs")
    os.makedirs(graph_dir, exist_ok=True)
    return os.path.join(graph_dir, f"scenario_graph_{uuid.uuid4().hex}.json")


def _layout_new_scenario_nodes(base_graph, added_nodes):
    if not added_nodes:
        return
    spacing_x = 240
    spacing_y = 180
    start_x = 200
    start_y = 200
    columns = 4

    used_cells = set()
    for node in base_graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if node in added_nodes:
            continue
        x = node.get("x")
        y = node.get("y")
        if x is None or y is None:
            continue
        col = round((x - start_x) / spacing_x)
        row = round((y - start_y) / spacing_y)
        used_cells.add((col, row))

    next_index = 0
    for node in added_nodes:
        while True:
            col = next_index % columns
            row = next_index // columns
            next_index += 1
            if (col, row) not in used_cells:
                used_cells.add((col, row))
                break
        node["x"] = start_x + col * spacing_x
        node["y"] = start_y + row * spacing_y


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


def _entity_link_key(link):
    node1_tag = link.get("node1_tag")
    node2_tag = link.get("node2_tag")
    sorted_tags = tuple(sorted((node1_tag, node2_tag)))
    return (
        sorted_tags[0],
        sorted_tags[1],
        link.get("text") or "",
        link.get("arrow_mode") or "both",
    )


def _normalize_link_tags(link):
    node1_tag = link.get("node1_tag")
    node2_tag = link.get("node2_tag")
    if not node1_tag or not node2_tag:
        if "npc_name1" in link and "npc_name2" in link:
            node1_tag = f"npc_{link['npc_name1'].replace(' ', '_')}"
            node2_tag = f"npc_{link['npc_name2'].replace(' ', '_')}"
        elif "pc_name1" in link and "pc_name2" in link:
            node1_tag = f"pc_{link['pc_name1'].replace(' ', '_')}"
            node2_tag = f"pc_{link['pc_name2'].replace(' ', '_')}"
    return node1_tag, node2_tag
