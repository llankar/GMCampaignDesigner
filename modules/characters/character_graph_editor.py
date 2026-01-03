import json
import math
import os
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk, Menu

from modules.audio.entity_audio import (
    get_entity_audio_value,
    play_entity_audio,
    stop_entity_audio,
)
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers import theme_manager
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import
from modules.helpers.portrait_helper import primary_portrait, resolve_portrait_path
from modules.helpers.template_loader import load_template
from modules.npcs import npc_opener
from modules.pcs import pc_opener
from modules.scenarios.scene_flow_rendering import (
    SCENE_FLOW_BG,
    apply_scene_flow_canvas_styling,
)
from modules.ui.image_viewer import show_portrait
from modules.characters.graph_tabs import (
    ManageGraphTabsDialog,
    build_default_tab,
    ensure_graph_tabs,
    filter_graph_for_tab,
    get_active_tab,
    merge_graph_into,
    set_active_tab,
)

log_module_import(__name__)

ctk.set_appearance_mode("Dark")
theme_manager.apply_theme(theme_manager.get_theme())

#logging.basicConfig(level=logging.ERROR)

# Constants for portrait folder and max portrait size
PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)
GRAPH_STORAGE_DIR = os.path.join(ConfigHelper.get_campaign_dir(), "graphs")
DEFAULT_CHARACTER_GRAPH_PATH = os.path.join(GRAPH_STORAGE_DIR, "character_graph.json")
NODE_TAG_PREFIXES = ("npc_", "pc_")

# ─────────────────────────────────────────────────────────────────────────
# CLASS: CharacterGraphEditor
# A custom graph editor for NPCs and PCs using CustomTkinter.
# Supports adding nodes, links, dragging, context menus, and saving/loading.
# ─────────────────────────────────────────────────────────────────────────
class CharacterGraphEditor(ctk.CTkFrame):
    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: __init__
    # Initializes the editor, loads data, sets up graph structures, canvas,
    # scrollbars, and event bindings.
    # ─────────────────────────────────────────────────────────────────────────
    def __init__(
        self,
        master,
        npc_wrapper: GenericModelWrapper,
        pc_wrapper: GenericModelWrapper,
        faction_wrapper: GenericModelWrapper,
        allowed_entity_types=None,
        graph_path=None,
        background_style="corkboard",
        node_style="postit",
        *args,
        **kwargs,
    ):
        super().__init__(master, *args, **kwargs)
        self.selected_shape = None
        self.link_canvas_ids = {}
        self.npc_wrapper = npc_wrapper
        self.pc_wrapper = pc_wrapper
        self.faction_wrapper = faction_wrapper
        self.allowed_entity_types = set(allowed_entity_types or ("npc", "pc"))
        self.entity_wrappers = {
            "npc": self.npc_wrapper,
            "pc": self.pc_wrapper,
        }
        self.entity_records = {"npc": {}, "pc": {}}
        self.entity_records_normalized = {"npc": {}, "pc": {}}
        for etype in self.allowed_entity_types:
            if etype in self.entity_records:
                self._refresh_entity_records(etype)
        self.graph_path = graph_path or DEFAULT_CHARACTER_GRAPH_PATH
        self.canvas_scale = 1.0
        self.zoom_factor = 1.1
        self.background_style = (background_style or "scene_flow").lower()
        self.node_style = (node_style or "postit").lower()
        # Graph structure to hold nodes and links
        self.graph = {
            "nodes": [],
            "links": [],
            "shapes": []  # 
        }
        ensure_graph_tabs(self.graph)
        self.original_positions = {}  # Backup for original character positions
        self.original_shape_positions = {}  # Backup for shapes
       
        self.shapes = {}  # this is for managing shape canvas objects
        self.shape_counter = 0  # if not already added

       
        # Dictionaries for node data
        self.node_positions = {}  # Current (x, y) positions of nodes
        self.node_images = {}     # Loaded images for node portraits
        self.node_rectangles = {} # Canvas rectangle IDs (for color changes)
        self.node_bboxes = {}     # Bounding boxes for nodes (used for arrow offsets)
        self.shape_counter = 0  # For unique shape tags
        self.node_holder_images = {}  # PhotoImage refs for post-it & overlay images
        self._grid_tile_cache = {}
        self._scene_flow_tile = None
        self._corkboard_base = None
        self._corkboard_photo = None
        self._corkboard_id = None
        # Variables for selection and dragging
        self.selected_node = None
        self.selected_items = []  # All canvas items belonging to the selected node
        self.drag_start = None    # Starting point for dragging
        self.selected_link = None # Currently selected link for context menus
        self.tab_selector_var = ctk.StringVar()
        self.tab_selector = None
        self.tab_id_by_name = {}
        self.nodes_collapsed = True
        
        # Initialize the toolbar and canvas frame
        self.init_toolbar()
        self.canvas_frame = ctk.CTkFrame(self)
        self.canvas_frame.pack(fill="both", expand=True)
        canvas_bg = SCENE_FLOW_BG if self.background_style == "scene_flow" else "#2B2B2B"
        self.canvas = ctk.CTkCanvas(self.canvas_frame, bg=canvas_bg, highlightthickness=0)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        
        # — ADDED: Post-it style assets
        postit_path = os.path.join("assets", "images", "post-it.png")
        pin_path    = os.path.join("assets", "images", "thumbtack.png")
        if self.node_style == "postit" and os.path.exists(postit_path):
            self.postit_base = Image.open(postit_path).convert("RGBA")
        else:
            self.postit_base = None

        if self.node_style == "postit" and os.path.exists(pin_path):
            pin_img = Image.open(pin_path)
            size = int(32 * self.canvas_scale)
            pin_img = pin_img.resize((size, size), Image.Resampling.LANCZOS)
            self.pin_image = ImageTk.PhotoImage(pin_img, master=self.canvas)
        else:
            self.pin_image = None

        # draw scene flow background once the canvas exists
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Bind mouse events for dragging and context menus
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        
        # Bind mouse wheel scrolling (Windows and Linux)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_y)
        self.canvas.bind("<Shift-MouseWheel>", self._on_mousewheel_x)
        self.canvas.bind("<Button-4>", self._on_mousewheel_y)
        self.canvas.bind("<Button-5>", self._on_mousewheel_y)
        self.canvas.bind("<Shift-Button-4>", self._on_mousewheel_x)
        self.canvas.bind("<Shift-Button-5>", self._on_mousewheel_x)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom)  # Windows
        self.canvas.bind("<Control-Button-4>", self._on_zoom)    # Linux scroll up
        self.canvas.bind("<Control-Button-5>", self._on_zoom)    # Linux scroll down
    # Bind double-click on any character element to open the editor window
        self.canvas.bind("<Double-Button-1>", self.open_character_editor)
        self.canvas.tag_bind("collapse_toggle", "<Button-1>", self.on_toggle_collapse, add="+")
        self._is_panning = False
        self.canvas.bind("<Button-2>", self._start_canvas_pan)
        self.canvas.bind("<B2-Motion>", self._do_canvas_pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_canvas_pan)
        self.pending_entity = None

        os.makedirs(GRAPH_STORAGE_DIR, exist_ok=True)
        if os.path.exists(self.graph_path):
            self.load_graph(self.graph_path)
        self._refresh_tab_selector()

    def _is_node_tag(self, tag):
        return tag.startswith(NODE_TAG_PREFIXES)

    def _extract_node_tag(self, tags):
        return next((t for t in tags if self._is_node_tag(t)), None)

    def _get_node_by_tag(self, tag):
        return next((node for node in self.graph["nodes"] if node.get("tag") == tag), None)

    def on_toggle_collapse(self, event):
        item = self.canvas.find_withtag("current")
        if not item:
            return "break"
        tags = self.canvas.gettags(item[0])
        node_tag = self._extract_node_tag(tags)
        if not node_tag:
            return "break"
        node = self._get_node_by_tag(node_tag)
        if not node:
            return "break"
        node["collapsed"] = not node.get("collapsed", False)
        self.nodes_collapsed = all(node.get("collapsed", True) for node in self.graph["nodes"])
        self.draw_graph()
        self._autosave_graph()
        return "break"

    def _add_node_to_active_tab(self, tag):
        active_tab = get_active_tab(self.graph)
        subset = active_tab.get("subsetDefinition") or {}
        if subset.get("mode") == "all":
            return
        node_tags = list(subset.get("node_tags") or [])
        if tag not in node_tags:
            node_tags.append(tag)
        subset["mode"] = "subset"
        subset["node_tags"] = node_tags
        active_tab["subsetDefinition"] = subset

    def _normalize_entity_name(self, name):
        """Return a lenient, lowercased name key resilient to extra spaces/punctuation."""
        if name is None:
            return ""
        text = str(name)
        # Unify dash variants and dots, collapse whitespace, strip punctuation and spaces.
        text = (
            text.replace("\u2013", "-")
            .replace("\u2014", "-")
            .replace(".", " ")
        )
        text = " ".join(text.split())  # collapse whitespace
        text = text.strip(" ,;:!-–—\t\r\n")
        return text.lower()

    def _normalize_entity_key(self, entity_type, entity_name):
        return (entity_type, self._normalize_entity_name(entity_name))

    def _find_tag_for_entity(self, tag_lookup, entity_type, entity_name):
        """Lookup a tag using forgiving name matching (handles trailing spaces/dots/variants)."""
        norm = self._normalize_entity_name(entity_name)
        tag = tag_lookup.get((entity_type, norm))
        if tag:
            return tag
        # Fallback: partial match either way (covers extra descriptors).
        for (etype, key_norm), candidate_tag in tag_lookup.items():
            if etype != entity_type:
                continue
            if norm.startswith(key_norm) or key_norm.startswith(norm):
                return candidate_tag
        return None

    def _get_entity_record(self, entity_type, entity_name):
        if not entity_name:
            return None
        records = self.entity_records.get(entity_type, {})
        if entity_name in records:
            return records.get(entity_name)
        norm = self._normalize_entity_name(entity_name)
        norm_records = self.entity_records_normalized.get(entity_type, {})
        if norm in norm_records:
            return norm_records.get(norm)
        for key_norm, record in norm_records.items():
            if norm.startswith(key_norm) or key_norm.startswith(norm):
                return record
        return None

    def _refresh_entity_records(self, entity_type):
        wrapper = self.entity_wrappers.get(entity_type)
        if not wrapper:
            return
        records = {}
        normalized = {}
        for item in wrapper.load_items():
            name = item.get("Name")
            if not name:
                continue
            records[name] = item
            norm = self._normalize_entity_name(name)
            if norm and norm not in normalized:
                normalized[norm] = item
        self.entity_records[entity_type] = records
        self.entity_records_normalized[entity_type] = normalized

    def _entity_type_to_table(self, entity_type):
        if entity_type == "npc":
            return "npcs"
        if entity_type == "pc":
            return "pcs"
        return None

    def _load_entity_wrapper(self, entity_type):
        table = self._entity_type_to_table(entity_type)
        if not table:
            return None
        return GenericModelWrapper(table)

    def _load_entity_record_from_db(self, entity_type, entity_name):
        wrapper = self._load_entity_wrapper(entity_type)
        if not wrapper:
            return None
        return wrapper.load_item_by_key(entity_name)

    def _save_entity_record(self, entity_type, record):
        wrapper = self._load_entity_wrapper(entity_type)
        if not wrapper:
            return
        wrapper.save_item(record)
        if isinstance(record, dict):
            name = record.get("Name")
            if name:
                self.entity_records.setdefault(entity_type, {})[name] = record
                norm = self._normalize_entity_name(name)
                if norm:
                    self.entity_records_normalized.setdefault(entity_type, {})[norm] = record

    def _get_node_entity_info(self, tag):
        node = self._get_node_by_tag(tag)
        if not node:
            return None
        entity_type = node.get("entity_type")
        entity_name = node.get("entity_name")
        if not entity_type or not entity_name:
            return None
        return entity_type, entity_name

    def _normalize_links_list(self, record):
        if not isinstance(record, dict):
            return []
        links = record.get("Links")
        if isinstance(links, list):
            return links
        return []

    def _upsert_link_entry(self, record, target_type, target_name, label, arrow_mode):
        if not isinstance(record, dict):
            return False
        links = self._normalize_links_list(record)
        for link in links:
            if not isinstance(link, dict):
                continue
            if (
                link.get("target_type") == target_type
                and link.get("target_name") == target_name
                and link.get("label") == label
            ):
                if arrow_mode and link.get("arrow_mode") != arrow_mode:
                    link["arrow_mode"] = arrow_mode
                    record["Links"] = links
                    return True
                record["Links"] = links
                return False
        links.append({
            "target_type": target_type,
            "target_name": target_name,
            "label": label,
            "arrow_mode": arrow_mode or "both",
        })
        record["Links"] = links
        return True

    def _remove_link_entry(self, record, target_type, target_name, label):
        if not isinstance(record, dict):
            return False
        links = self._normalize_links_list(record)
        if not links:
            return False
        new_links = []
        removed = False
        for link in links:
            if not isinstance(link, dict):
                new_links.append(link)
                continue
            if (
                link.get("target_type") == target_type
                and link.get("target_name") == target_name
                and link.get("label") == label
            ):
                removed = True
                continue
            new_links.append(link)
        if removed:
            record["Links"] = new_links
        return removed

    def _persist_link_to_entities(self, link):
        node1 = self._get_node_entity_info(link.get("node1_tag"))
        node2 = self._get_node_entity_info(link.get("node2_tag"))
        if not node1 or not node2:
            return
        entity_type1, entity_name1 = node1
        entity_type2, entity_name2 = node2
        label = link.get("text") or ""
        arrow_mode = link.get("arrow_mode") or "both"
        record1 = self._load_entity_record_from_db(entity_type1, entity_name1)
        if record1:
            changed = self._upsert_link_entry(
                record1,
                entity_type2,
                entity_name2,
                label,
                arrow_mode,
            )
            if changed:
                self._save_entity_record(entity_type1, record1)
        record2 = self._load_entity_record_from_db(entity_type2, entity_name2)
        if record2:
            changed = self._upsert_link_entry(
                record2,
                entity_type1,
                entity_name1,
                label,
                arrow_mode,
            )
            if changed:
                self._save_entity_record(entity_type2, record2)

    def _remove_link_from_entities(self, link):
        node1 = self._get_node_entity_info(link.get("node1_tag"))
        node2 = self._get_node_entity_info(link.get("node2_tag"))
        if not node1 or not node2:
            return
        entity_type1, entity_name1 = node1
        entity_type2, entity_name2 = node2
        label = link.get("text") or ""
        record1 = self._load_entity_record_from_db(entity_type1, entity_name1)
        if record1:
            removed = self._remove_link_entry(
                record1,
                entity_type2,
                entity_name2,
                label,
            )
            if removed:
                self._save_entity_record(entity_type1, record1)
        record2 = self._load_entity_record_from_db(entity_type2, entity_name2)
        if record2:
            removed = self._remove_link_entry(
                record2,
                entity_type1,
                entity_name1,
                label,
            )
            if removed:
                self._save_entity_record(entity_type2, record2)

    def _rebuild_links_from_entities(self):
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
        rebuilt_links = []
        seen = set()
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
                link_key = tuple(sorted((tag, target_tag))) + (label,)
                if link_key in seen:
                    continue
                seen.add(link_key)
                rebuilt_links.append({
                    "node1_tag": tag,
                    "node2_tag": target_tag,
                    "text": label,
                    "arrow_mode": link.get("arrow_mode") or "both",
                })
        self.graph["links"] = rebuilt_links

    def _link_key(self, link):
        if not isinstance(link, dict):
            return None
        tag1 = link.get("node1_tag")
        tag2 = link.get("node2_tag")
        if not tag1 or not tag2:
            return None
        label = link.get("text") or ""
        return tuple(sorted((tag1, tag2))) + (label,)

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
            self._link_key(link)
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
                link_key = self._link_key(link_data)
                if link_key in existing_keys:
                    continue
                existing_keys.add(link_key)
                new_links.append(link_data)
        if new_links:
            self.graph.setdefault("links", []).extend(new_links)
            return True
        return False

    def _get_entity_opener(self, entity_type):
        if entity_type == "pc":
            return pc_opener.open_pc_editor_window
        return npc_opener.open_npc_editor_window

    def _on_zoom(self, event):
        if event.delta > 0 or event.num == 4:
            scale = self.zoom_factor
        else:
            scale = 1 / self.zoom_factor

        new_scale = self.canvas_scale * scale
        new_scale = max(0.5, min(new_scale, 2.5))
        scale_change = new_scale / self.canvas_scale
        self.canvas_scale = new_scale

        # Use mouse as zoom anchor
        anchor_x = self.canvas.canvasx(event.x)
        anchor_y = self.canvas.canvasy(event.y)

        # Update positions
        for tag, (x, y) in self.node_positions.items():
            dx = x - anchor_x
            dy = y - anchor_y
            new_x = anchor_x + dx * scale_change
            new_y = anchor_y + dy * scale_change
            self.node_positions[tag] = (new_x, new_y)
            for node in self.graph["nodes"]:
                node_tag = node.get("tag")
                if node_tag == tag:
                    node["x"], node["y"] = new_x, new_y
                    break

        # Also apply to shapes
        for tag, shape in self.shapes.items():
            dx = shape["x"] - anchor_x
            dy = shape["y"] - anchor_y
            shape["x"] = anchor_x + dx * scale_change
            shape["y"] = anchor_y + dy * scale_change

        self.draw_graph()
        self._autosave_graph()
 # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: open_character_editor
    # Opens the Generic Editor Window for the clicked character.
    # ─────────────────────────────────────────────────────────────────────────
    def open_character_editor(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        node_tag = self._extract_node_tag(tags)
        if not node_tag:
            return
        node = self._get_node_by_tag(node_tag)
        if not node:
            messagebox.showerror("Error", "Character not found in graph.")
            return
        entity_type = node.get("entity_type")
        entity_name = node.get("entity_name")
        opener = self._get_entity_opener(entity_type)
        print(f"Opening editor for {entity_type.upper()}: {entity_name}")
        opener(entity_name)
        # ─────────────────────────────────────────────────────────────────────────
    def display_portrait_window(self):
        """Display the character's portrait in a normal window (with decorations) that is
        sized and positioned to cover the second monitor (if available).
        """
        #logging.debug("Entering display_portrait_window")

        if not self.selected_node or not self._is_node_tag(self.selected_node):
            messagebox.showerror("Error", "No character selected.")
            return

        node = self._get_node_by_tag(self.selected_node)
        if not node:
            messagebox.showerror("Error", "Character not found in graph.")
            return

        entity_type = node.get("entity_type")
        entity_name = node.get("entity_name")
        entity_data = self._get_entity_record(entity_type, entity_name)
        if not entity_data:
            messagebox.showerror("Error", f"{entity_type.upper()} '{entity_name}' not found.")
            return

        portrait_path = primary_portrait(entity_data.get("Portrait", ""))
        resolved_portrait = resolve_portrait_path(portrait_path, ConfigHelper.get_campaign_dir())
        if not resolved_portrait or not os.path.exists(resolved_portrait):
            messagebox.showerror("Error", "No valid portrait found for this character.")
            return
        show_portrait(portrait_path, entity_name)

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: _on_mousewheel_y
    # Scrolls the canvas vertically based on mouse wheel input.
    # ─────────────────────────────────────────────────────────────────────────
    def _on_mousewheel_y(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def get_state(self):
        return {
            "graph": self.graph.copy(),
            "node_positions": self.node_positions.copy(),
            # include any other state needed
        }

    def set_state(self, state):
        self.graph = state.get("graph", {}).copy()
        ensure_graph_tabs(self.graph)
        self.node_positions = state.get("node_positions", {}).copy()
        self._refresh_tab_selector()
        self.draw_graph()  # Refresh the drawing

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: _on_mousewheel_x
    # Scrolls the canvas horizontally based on mouse wheel input.
    # ─────────────────────────────────────────────────────────────────────────
    def _on_mousewheel_x(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.xview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.xview_scroll(1, "units")

    def _start_canvas_pan(self, event):
        self._is_panning = True
        self.canvas.scan_mark(event.x, event.y)

    def _do_canvas_pan(self, event):
        if not self._is_panning:
            return
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _end_canvas_pan(self, _event):
        self._is_panning = False

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: init_toolbar
    # Creates a toolbar with buttons for adding characters, factions, saving, loading, and adding links.
    # ─────────────────────────────────────────────────────────────────────────
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
            text="Add Faction",
            command=self.add_faction,
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Add Link",
            command=self.start_link_creation,
            **button_kwargs,
        ).pack(side="left", padx=5)

        # 🆕 Add Shape Buttons
        ctk.CTkButton(
            toolbar,
            text="Add Rectangle",
            command=lambda: self.add_shape("rectangle"),
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Add Oval",
            command=lambda: self.add_shape("oval"),
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="+/-",
            command=self.toggle_nodes_collapsed,
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Reset Zoom",
            command=self.reset_zoom,
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkLabel(toolbar, text="Tab:").pack(side="left", padx=(15, 5))
        self.tab_selector = ctk.CTkOptionMenu(
            toolbar,
            variable=self.tab_selector_var,
            values=[],
            command=self._on_tab_selected,
            width=160,
        )
        self.tab_selector.pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Manage Tabs",
            command=self.open_manage_tabs,
            **button_kwargs,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Load JSON",
            command=self.load_graph_into_tab,
            **button_kwargs,
        ).pack(side="left", padx=5)

    def toggle_nodes_collapsed(self):
        self.nodes_collapsed = not self.nodes_collapsed
        for node in self.graph["nodes"]:
            node["collapsed"] = self.nodes_collapsed
        self.draw_graph()
        self._autosave_graph()

    def reset_zoom(self):
        self.canvas_scale = 1.0

        # Restore node positions
        for node in self.graph["nodes"]:
            tag = node.get("tag")
            if tag in self.original_positions:
                x, y = self.original_positions[tag]
                node["x"], node["y"] = x, y
                self.node_positions[tag] = (x, y)

        # Restore shape positions
        for shape in self.graph.get("shapes", []):
            tag = shape["tag"]
            if tag in self.original_shape_positions:
                x, y = self.original_shape_positions[tag]
                shape["x"], shape["y"] = x, y

        self.draw_graph()
        self._autosave_graph()

    def _refresh_tab_selector(self):
        ensure_graph_tabs(self.graph)
        tabs = self.graph.get("tabs", [])
        self.tab_id_by_name = {}
        display_names = []
        for tab in tabs:
            name = tab.get("name", "Tab")
            if name in self.tab_id_by_name:
                suffix = 2
                candidate = f"{name} ({suffix})"
                while candidate in self.tab_id_by_name:
                    suffix += 1
                    candidate = f"{name} ({suffix})"
                name = candidate
            self.tab_id_by_name[name] = tab.get("id")
            display_names.append(name)

        if self.tab_selector:
            self.tab_selector.configure(values=display_names)
            active_tab = get_active_tab(self.graph)
            active_name = next(
                (name for name, tab_id in self.tab_id_by_name.items() if tab_id == active_tab.get("id")),
                display_names[0] if display_names else "",
            )
            if active_name:
                self.tab_selector_var.set(active_name)

    def _on_tab_selected(self, selected_name):
        tab_id = self.tab_id_by_name.get(selected_name)
        if tab_id:
            set_active_tab(self.graph, tab_id)
        self.draw_graph()
        self._autosave_graph()

    def open_manage_tabs(self):
        ManageGraphTabsDialog(self, self.graph, on_update=self._on_tabs_updated)

    def _on_tabs_updated(self):
        self._refresh_tab_selector()
        self.draw_graph()
        self._autosave_graph()

    def _unique_tab_name(self, base_name, current_tab=None):
        existing = {tab.get("name") for tab in self.graph.get("tabs", []) if tab is not current_tab}
        name = base_name
        suffix = 2
        while name in existing:
            name = f"{base_name} ({suffix})"
            suffix += 1
        return name

    def load_graph_into_tab(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json")],
            title="Load Character Graph JSON",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                imported_graph = json.load(file)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Could not load file:\n{exc}")
            return
        try:
            merge_result = merge_graph_into(
                self.graph,
                imported_graph,
                self.nodes_collapsed,
                self.shape_counter,
            )
        except ValueError as exc:
            messagebox.showerror("Load Error", str(exc))
            return

        for node in merge_result.imported_nodes:
            self.graph["nodes"].append(node)
            tag = node.get("tag")
            if tag:
                self.node_positions[tag] = (node.get("x", 0), node.get("y", 0))
                self.original_positions[tag] = (node.get("x", 0), node.get("y", 0))

        for link in merge_result.imported_links:
            self.graph["links"].append(link)

        for shape in merge_result.imported_shapes:
            self.graph.setdefault("shapes", []).append(shape)
            tag = shape.get("tag")
            if tag:
                self.shapes[tag] = shape
                self.original_shape_positions[tag] = (shape.get("x", 0), shape.get("y", 0))

        self.shape_counter = merge_result.shape_counter

        base_name = os.path.splitext(os.path.basename(path))[0] or "Imported"
        tab = build_default_tab()
        tab["name"] = self._unique_tab_name(base_name, current_tab=tab)
        tab["subsetDefinition"] = {"mode": "subset", "node_tags": merge_result.imported_node_tags}
        self.graph.setdefault("tabs", []).append(tab)
        self.graph["active_tab_id"] = tab["id"]

        self._refresh_tab_selector()
        self.draw_graph()
        self._autosave_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: start_link_creation
    # Temporarily rebinds left-click to select the first node for a new link.
    # ─────────────────────────────────────────────────────────────────────────
    def start_link_creation(self):
        self.canvas.bind("<Button-1>", self.select_first_node)

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: select_first_node
    # Selects the first node for a new link based on the nearest canvas item.
    # ─────────────────────────────────────────────────────────────────────────
    def select_first_node(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        self.first_node = self._extract_node_tag(tags)
        if self.first_node:
            self.canvas.bind("<Button-1>", self.select_second_node)

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: select_second_node
    # Selects the second node for a new link and then opens the link text dialog.
    # ─────────────────────────────────────────────────────────────────────────
    def select_second_node(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        self.second_node = self._extract_node_tag(tags)
        if self.second_node:
            self.canvas.unbind("<Button-1>")
            self.prompt_link_text()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: prompt_link_text
    # Opens a dialog for the user to enter link text, then adds the link.
    # ─────────────────────────────────────────────────────────────────────────
    def prompt_link_text(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Enter Link Text")
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        ctk.CTkLabel(dialog, text="Link Text:").pack(pady=5)
        link_text_var = ctk.StringVar()
        link_text_entry = ctk.CTkEntry(dialog, textvariable=link_text_var)
        link_text_entry.pack(pady=5)
        link_text_entry.bind("<Return>", lambda event: on_add_link())
        def on_add_link():
            link_text = link_text_var.get()
            self.add_link(self.first_node, self.second_node, link_text)
            dialog.destroy()
            self.canvas.bind("<Button-1>", self.start_drag)
        ctk.CTkButton(dialog, text="Add Link", command=on_add_link).pack(pady=10)
        dialog.after(100, link_text_entry.focus_set)

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_link
    # Adds a new link between two nodes with the specified link text.
    # ─────────────────────────────────────────────────────────────────────────
    def add_link(self, tag1, tag2, link_text):
        if tag1 not in self.node_positions or tag2 not in self.node_positions:
            messagebox.showerror("Error", "One or both characters not found.")
            return
        for existing in self.graph["links"]:
            if (
                existing.get("text") == link_text
                and (
                    (existing.get("node1_tag") == tag1 and existing.get("node2_tag") == tag2)
                    or (existing.get("node1_tag") == tag2 and existing.get("node2_tag") == tag1)
                )
            ):
                self._persist_link_to_entities(existing)
                self.draw_graph()
                self._autosave_graph()
                return
        new_link = {
            "node1_tag": tag1,
            "node2_tag": tag2,
            "text": link_text,
            "arrow_mode": "both"  # Options: "none", "start", "end", "both"
        }
        self.graph["links"].append(new_link)
        self._persist_link_to_entities(new_link)
        self.draw_graph()
        self._autosave_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_entity
    # Opens a selection dialog and binds the next click to place the character.
    # ─────────────────────────────────────────────────────────────────────────
    def add_entity(self, entity_type):
        if entity_type not in self.allowed_entity_types:
            return

        def on_entity_selected(entity_name):
            self._refresh_entity_records(entity_type)
            selected_entity = self._get_entity_record(entity_type, entity_name)
            if not selected_entity:
                messagebox.showerror("Error", f"{entity_type.upper()} '{entity_name}' not found.")
                return
            self.pending_entity = {"type": entity_type, "record": selected_entity}
            if dialog.winfo_exists():
                dialog.destroy()
            self.canvas.bind("<Button-1>", self.place_pending_entity)

        template_key = "npcs" if entity_type == "npc" else "pcs"
        display_name = "NPCs" if entity_type == "npc" else "PCs"
        template = load_template(template_key)
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Select {entity_type.upper()}")
        dialog.geometry("1200x800")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        selection_view = GenericListSelectionView(
            dialog,
            display_name,
            self.entity_wrappers[entity_type],
            template,
            on_select_callback=lambda _et, name: on_entity_selected(name),
        )
        selection_view.pack(fill="both", expand=True)
        dialog.wait_window()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: place_pending_entity
    # Places the selected character at the mouse click location and updates the graph.
    # ─────────────────────────────────────────────────────────────────────────
    def place_pending_entity(self, event):
        entity = self.pending_entity
        if not entity:
            return
        entity_type = entity["type"]
        entity_name = entity["record"]["Name"]

        x0 = self.canvas.canvasx(event.x)
        y0 = self.canvas.canvasy(event.y)
        base = f"{entity_type}_{entity_name.replace(' ', '_')}"
        tag = base
        i = 1
        while tag in self.node_positions:
            tag = f"{base}_{i}"
            i += 1

        self.graph["nodes"].append({
            "entity_type": entity_type,
            "entity_name": entity_name,
            "tag": tag,
            "x": x0,
            "y": y0,
            "collapsed": self.nodes_collapsed,
        })
        self.node_positions[tag] = (x0, y0)
        self._add_node_to_active_tab(tag)

        self.pending_entity = None
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.start_drag)
        self._merge_links_from_entities()
        self.draw_graph()
        self._autosave_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_faction
    # Opens a faction selection dialog and adds all characters from the selected faction.
    # ─────────────────────────────────────────────────────────────────────────
    def add_faction(self):
        # ── 1) Show a modal dialog to pick a faction ─────────────────────
        popup = ctk.CTkToplevel(self)
        popup.title("Select Faction")
        popup.geometry("400x300")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()

        # We only need to display the “Name” field of each faction
        faction_template = {"fields": [{"name": "Name", "type": "text"}]}

        # ── 2) Callback when the user double-clicks a faction ────────────
        def on_faction_selected(entity_type, faction_name):
            # close the dialog
            if popup.winfo_exists():
                popup.destroy()

            faction_characters = []
            for character_type in self.allowed_entity_types:
                self._refresh_entity_records(character_type)
                for record in self.entity_records.get(character_type, {}).values():
                    faction_value = record.get("Factions")
                    if isinstance(faction_value, list) and faction_name in faction_value:
                        faction_characters.append((character_type, record))
                    elif faction_value == faction_name:
                        faction_characters.append((character_type, record))

            if not faction_characters:
                messagebox.showinfo("No Characters", f"No characters found in faction '{faction_name}'.")
                return

            # ── 3) Place each character as its own post-it ─────────────────────
            start_x, start_y = 100, 100
            spacing = int(120 * self.canvas_scale)
            for i, (character_type, record) in enumerate(faction_characters):
                name = record["Name"]
                # generate a unique tag
                base = f"{character_type}_{name.replace(' ', '_')}"
                tag = base
                suffix = 1
                while tag in self.node_positions:
                    tag = f"{base}_{suffix}"
                    suffix += 1

                x = start_x + i * spacing
                y = start_y

                # record in the underlying graph
                self.graph["nodes"].append({
                    "entity_type": character_type,
                    "entity_name": name,
                    "tag": tag,
                    "x": x,
                    "y": y,
                    "color": "#1D3572",
                    "collapsed": self.nodes_collapsed,
                })
                # record its canvas position
                self.node_positions[tag] = (x, y)
                self._add_node_to_active_tab(tag)

            # ── 4) Restore drag handlers so these new nodes can be moved ───
            self.canvas.unbind("<Button-1>")
            self.canvas.bind("<Button-1>",        self.start_drag)
            self.canvas.bind("<B1-Motion>",       self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.end_drag)

            # ── 5) Redraw everything (post-its, portraits, links, etc.) ────
            self._merge_links_from_entities()
            self.draw_graph()
            self._autosave_graph()

        # ── 6) Instantiate the actual list view with your faction_wrapper ──
        view = GenericListSelectionView(
            master=popup,
            entity_type="Faction",
            model_wrapper=self.faction_wrapper,
            template=faction_template,
            on_select_callback=on_faction_selected
        )
        view.pack(fill="both", expand=True)

        # block until the popup is closed
        popup.wait_window()

    def update_links_positions_for_node(self, node_tag):
        for link in self.graph["links"]:
            if node_tag in (link.get("node1_tag"), link.get("node2_tag")):
                key = (link.get("node1_tag"), link.get("node2_tag"))
                canvas_ids = self.link_canvas_ids.get(key)
                if canvas_ids:
                    tag1 = link.get("node1_tag")
                    tag2 = link.get("node2_tag")
                    x1, y1 = self.node_positions.get(tag1, (0, 0))
                    x2, y2 = self.node_positions.get(tag2, (0, 0))
                    start_x, start_y = self._get_edge_point(tag1, x2, y2)
                    end_x, end_y = self._get_edge_point(tag2, x1, y1)
                    link_color, line_width = self._get_link_style(link)

                    # Update line coordinates directly
                    self.canvas.coords(canvas_ids["line"], start_x, start_y, end_x, end_y)
                    self.canvas.itemconfig(canvas_ids["line"], fill=link_color, width=line_width)

                    # Update text position
                    mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
                    self.canvas.coords(canvas_ids["text"], mid_x, mid_y)

                    # Delete old arrowheads
                    for arrow_id in canvas_ids["arrows"]:
                        self.canvas.delete(arrow_id)
                    canvas_ids["arrows"] = []

                    # Redraw arrowheads at new position
                    arrow_mode = link.get("arrow_mode", "end")
                    if arrow_mode in ("start", "both"):
                        arrow_id = self.draw_arrowhead(tag1, x2, y2, link_color)
                        canvas_ids["arrows"].append(arrow_id)
                    if arrow_mode in ("end", "both"):
                        arrow_id = self.draw_arrowhead(tag2, x1, y1, link_color)
                        canvas_ids["arrows"].append(arrow_id)

    
    def update_links_for_node(self, node_tag):
        # Delete only existing links and associated arrowheads/text
        self.canvas.delete("link")
        self.canvas.delete("arrowhead")
        self.canvas.delete("link_text")

        # Redraw only links involving the moved node
        affected_links = [
            link for link in self.graph["links"]
            if node_tag in (link.get("node1_tag"), link.get("node2_tag"))
        ]
        for link in affected_links:
            self.draw_one_link(link)

        self.canvas.tag_lower("link")
        self.canvas.tag_raise("arrowhead")
        self.canvas.tag_raise("link_text")
    
    def delete_shape(self, tag):
        # Delete from canvas
        self.canvas.delete(tag)
        # Delete from internal storage
        if tag in self.shapes:
            del self.shapes[tag]
        self.graph["shapes"] = [s for s in self.graph["shapes"] if s["tag"] != tag]
        self._autosave_graph()
    

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: on_right_click
    # Determines whether a link or node was right-clicked and displays the appropriate context menu.
    # ─────────────────────────────────────────────────────────────────────────
    def on_right_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return

        tags = self.canvas.gettags(item[0])
        if "link" in tags or "link_text" in tags or "arrowhead" in tags:
            self.selected_link = self.get_link_by_position(x, y)
            self.show_link_menu(int(x), int(y))
        elif any(self._is_node_tag(tag) for tag in tags):
            self.selected_node = self._extract_node_tag(tags)
            self.show_node_menu(x, y)
        elif any(tag.startswith("shape_") for tag in tags):
            shape_tag = next((t for t in tags if t.startswith("shape_")), None)
            if shape_tag:
                self.show_shape_menu(x, y, shape_tag)


    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: show_color_menu
    # Displays a color selection menu for changing the node color.
    # ─────────────────────────────────────────────────────────────────────────
    def show_color_menu(self, x, y):
        COLORS = [
            "red", "green", "blue", "yellow", "purple",
            "orange", "pink", "cyan", "magenta", "lightgray"
        ]
        color_menu = Menu(self.canvas, tearoff=0)
        for color in COLORS:
            color_menu.add_command(label=color, command=lambda c=color: self.change_node_color(c))
        color_menu.post(int(x), int(y))

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: show_link_menu
    # Displays a context menu for links with a submenu for arrow mode selection.
    # ─────────────────────────────────────────────────────────────────────────
    def show_link_menu(self, x, y):
        link_menu = Menu(self.canvas, tearoff=0)
        arrow_submenu = Menu(link_menu, tearoff=0)
        arrow_submenu.add_command(label="No Arrows", command=lambda: self.set_arrow_mode("none"))
        arrow_submenu.add_command(label="Arrow at Start", command=lambda: self.set_arrow_mode("start"))
        arrow_submenu.add_command(label="Arrow at End", command=lambda: self.set_arrow_mode("end"))
        arrow_submenu.add_command(label="Arrows at Both Ends", command=lambda: self.set_arrow_mode("both"))
        link_menu.add_cascade(label="Arrow Mode", menu=arrow_submenu)
        link_menu.add_separator()
        link_menu.add_command(label="Delete Link", command=self.delete_link)
        link_menu.post(x, y)

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: show_node_menu
    # Displays a context menu for nodes with options to delete the node or change its color.
    # ─────────────────────────────────────────────────────────────────────────
    def show_node_menu(self, x, y):
        node_menu = Menu(self.canvas, tearoff=0)
        node_menu.add_command(label="Delete Node", command=self.delete_node)
        node_menu.add_separator()
        node_menu.add_command(label="Change Color", command=lambda: self.show_color_menu(x, y))
        node_menu.add_command(label="Display Portrait Window", command=self.display_portrait_window)
        record = None
        entity_name = None
        if self.selected_node:
            node = self._get_node_by_tag(self.selected_node)
            if node:
                entity_name = node.get("entity_name")
                record = self._get_entity_record(node.get("entity_type"), entity_name)
        audio_value = self._get_entity_audio(record)
        if audio_value:
            node_menu.add_separator()
            node_menu.add_command(
                label="Play Audio",
                command=lambda n=entity_name, r=record: self._play_entity_audio(r, n),
            )
            node_menu.add_command(label="Stop Audio", command=stop_entity_audio)
        node_menu.post(int(x), int(y))

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: set_arrow_mode
    # Sets the arrow_mode for the currently selected link.
    # ─────────────────────────────────────────────────────────────────────────
    def set_arrow_mode(self, new_mode):
        if not self.selected_link:
            return
        updated_link = None
        for link in self.graph["links"]:
            if (
                link.get("node1_tag") == self.selected_link.get("node1_tag")
                and link.get("node2_tag") == self.selected_link.get("node2_tag")
            ):
                link["arrow_mode"] = new_mode
                updated_link = link
                break
        if updated_link:
            self._persist_link_to_entities(updated_link)
        self.draw_graph()
        self._autosave_graph()

    def delete_link(self):
        if not self.selected_link:
            return
        link_to_remove = self.selected_link
        self._remove_link_from_entities(link_to_remove)
        self.graph["links"] = [
            link for link in self.graph["links"]
            if not self._link_matches(link, link_to_remove)
        ]
        self.selected_link = None
        self.draw_graph()
        self._autosave_graph()

    def _link_matches(self, link, other):
        if not isinstance(link, dict) or not isinstance(other, dict):
            return False
        link_nodes = {link.get("node1_tag"), link.get("node2_tag")}
        other_nodes = {other.get("node1_tag"), other.get("node2_tag")}
        return link_nodes == other_nodes and link.get("text") == other.get("text")

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: delete_node
    # Deletes the currently selected node and removes any links involving it.
    # ─────────────────────────────────────────────────────────────────────────
    def delete_node(self):
        if not self.selected_node:
            return

        tag = self.selected_node
        active_tab = get_active_tab(self.graph)
        subset = active_tab.get("subsetDefinition") or {}
        if subset.get("mode") != "all":
            node_tags = list(subset.get("node_tags") or [])
            if tag in node_tags:
                node_tags.remove(tag)
            subset["mode"] = "subset"
            subset["node_tags"] = node_tags
            active_tab["subsetDefinition"] = subset
            self.selected_node = None
            self.draw_graph()
            self._autosave_graph()
            return
        # 1) Remove all canvas items for this node (post-it, pin, portrait, text)
        self.canvas.delete(tag)

        # 2) Remove from the model
        self.graph["nodes"] = [
            n for n in self.graph["nodes"]
            if n.get("tag") != tag
        ]
        links_to_remove = [
            l for l in self.graph["links"]
            if tag in (l.get("node1_tag"), l.get("node2_tag"))
        ]
        for link in links_to_remove:
            self._remove_link_from_entities(link)
        self.graph["links"] = [
            l for l in self.graph["links"]
            if tag not in (l.get("node1_tag"), l.get("node2_tag"))
        ]

        # 3) Drop its saved position
        self.node_positions.pop(tag, None)

        # 4) Redraw the rest of the graph
        self.draw_graph()
        self._autosave_graph()

    def redraw_after_drag(self):
        self.draw_graph()

    def _get_entity_audio(self, record):
        return get_entity_audio_value(record)

    def _play_entity_audio(self, record, name):
        audio_value = self._get_entity_audio(record)
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this character.")
            return
        label = name or "Character"
        if not play_entity_audio(audio_value, entity_label=str(label)):
            messagebox.showwarning("Audio", f"Unable to play audio for {label}.")
        self._redraw_scheduled = False


    
        # — ADDED: draw the scene flow background once canvas exists
    def _apply_scene_flow_background(self, width=None, height=None):
        if not hasattr(self, "canvas"):
            return
        width = width or max(self.canvas.winfo_width(), 1)
        height = height or max(self.canvas.winfo_height(), 1)
        tile = apply_scene_flow_canvas_styling(
            self.canvas,
            tile_cache=self._grid_tile_cache,
            extent_width=width,
            extent_height=height,
        )
        if tile is not None:
            self._scene_flow_tile = tile
        self.canvas.tag_lower("scene_flow_bg")

    def _apply_corkboard_background(self, width=None, height=None):
        if not hasattr(self, "canvas"):
            return
        background_path = os.path.join("assets", "images", "corkboard_bg.png")
        if not os.path.exists(background_path):
            return
        width = width or max(self.canvas.winfo_width(), 1)
        height = height or max(self.canvas.winfo_height(), 1)
        if self._corkboard_base is None:
            self._corkboard_base = Image.open(background_path)
        zoom_factor = 2
        target_width = max(int(width), 1920) * zoom_factor
        target_height = max(int(height), 1080) * zoom_factor
        resized = self._corkboard_base.resize(
            (target_width, target_height),
            Image.Resampling.LANCZOS,
        )
        self._corkboard_photo = ImageTk.PhotoImage(resized, master=self.canvas)
        center_x = width // 2
        center_y = height // 2
        if self._corkboard_id is None:
            self._corkboard_id = self.canvas.create_image(
                center_x,
                center_y,
                image=self._corkboard_photo,
                anchor="center",
                tags="background",
            )
        else:
            self.canvas.itemconfig(self._corkboard_id, image=self._corkboard_photo)
            self.canvas.coords(self._corkboard_id, center_x, center_y)
        self.canvas.tag_lower("background")

    def _on_canvas_configure(self, event):
        """
        Whenever the canvas is resized (or we manually call this),
        redraw the background to fill the full width/height.
        """
        if self.background_style == "corkboard":
            self._apply_corkboard_background(event.width, event.height)
        else:
            self._apply_scene_flow_background(event.width, event.height)
    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_nodes
    # Iterates over all nodes in the graph, draws their rectangles, portraits, and labels,
    # and calculates/stores their bounding boxes.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_nodes(self, nodes):
        scale = self.canvas_scale
        node_style = (self.node_style or "postit").lower()
        GAP = int((6 if node_style == "modern" else 5) * scale)
        PAD = int((14 if node_style == "modern" else 10) * scale)

        def draw_rounded_panel(x1, y1, x2, y2, radius, **kwargs):
            radius = max(0, int(radius))
            points = [
                x1 + radius, y1,
                x2 - radius, y1,
                x2, y1,
                x2, y1 + radius,
                x2, y2 - radius,
                x2, y2,
                x2 - radius, y2,
                x1 + radius, y2,
                x1, y2,
                x1, y2 - radius,
                x1, y1 + radius,
                x1, y1,
            ]
            return self.canvas.create_polygon(points, smooth=True, **kwargs)

        # Helper to measure wrapped text height
        def measure_text_height(text, font, wrap_width):
            tid = self.canvas.create_text(
                0, 0,
                text=text,
                font=font,
                width=wrap_width,
                anchor="nw"
            )
            bbox = self.canvas.bbox(tid)
            self.canvas.delete(tid)
            return (bbox[3] - bbox[1]) if bbox else 0

        def measure_text_size(text, font, wrap_width=None):
            tid = self.canvas.create_text(
                0, 0,
                text=text,
                font=font,
                width=wrap_width or 0,
                anchor="nw"
            )
            bbox = self.canvas.bbox(tid)
            self.canvas.delete(tid)
            if not bbox:
                return 0, 0
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        for node in nodes:
            entity_type = node.get("entity_type")
            entity_name = node.get("entity_name")
            tag = node.get("tag")
            x, y = self.node_positions.get(tag, (node["x"], node["y"]))
            is_collapsed = node.get("collapsed", False)

            # ── Font definitions ─────────────────────────────────────
            title_font = ("Arial", max(1, int(10 * scale)), "bold")
            body_font  = ("Arial", max(1, int(9  * scale)))
            title_color = "#f0f4ff" if node_style == "modern" else "black"
            body_color = "#c7d2e3" if node_style == "modern" else "black"

            # ── Prepare title & body text ────────────────────────────
            title_text = entity_name

            if is_collapsed:
                title_w, title_h = measure_text_size(title_text, title_font)
                wrap_width = max(1, int(title_w))
                body_text = ""
                body_h = 0
                p_w = p_h = 0
                portrait_img = None

                content_w = title_w
                content_h = title_h
                min_w = content_w + 2 * PAD
                min_h = content_h + 2 * PAD
            else:
                # ── Load character data ───────────────────────────────────
                data = self._get_entity_record(entity_type, entity_name) or {}
                role = data.get("Role", "")
                fv = data.get("Factions", "")
                fv_text = ", ".join(fv) if isinstance(fv, list) else str(fv) if fv else ""
                body_text = "\n".join(filter(None, [role, fv_text]))

                # ── Load & scale portrait ─────────────────────────────────
                portrait_img = None
                p_w = p_h = 0
                portrait_path = primary_portrait(data.get("Portrait", ""))
                resolved_portrait = resolve_portrait_path(portrait_path, ConfigHelper.get_campaign_dir())
                if resolved_portrait and os.path.exists(resolved_portrait):
                    img = Image.open(resolved_portrait)
                    ow, oh = img.size
                    max_w = int(80 * scale)
                    max_h = int(80 * scale)
                    ratio = min(max_w / ow, max_h / oh, 1.0)
                    p_w, p_h = int(ow * ratio), int(oh * ratio)
                    img = img.resize((p_w, p_h), Image.Resampling.LANCZOS)
                    portrait_img = ImageTk.PhotoImage(img, master=self.canvas)
                    self.node_images[tag] = portrait_img

                # ── Compute wrap width & measure text heights ────────────
                wrap_width = max(p_w, int(160 * scale if node_style == "modern" else 150 * scale)) - 2 * PAD
                title_h = measure_text_height(title_text, title_font, wrap_width)
                body_h = measure_text_height(body_text, body_font, wrap_width) if body_text else 0

                # ── Compute content & node dimensions ────────────────────
                content_w = max(p_w, wrap_width)
                content_h = (
                    p_h
                    + (GAP if p_h > 0 and (title_h > 0 or body_h > 0) else 0)
                    + title_h
                    + (GAP if body_h > 0 else 0)
                    + body_h
                )
                min_w = content_w + 2 * PAD
                min_h = content_h + 2 * PAD

            # ── 1) Draw the node background ──────────────────────────
            if node_style == "modern":
                node_w, node_h = min_w, min_h
                shadow_offset = max(2, int(4 * scale))
                corner_radius = max(6, int(12 * scale))
                draw_rounded_panel(
                    x - node_w / 2 + shadow_offset,
                    y - node_h / 2 + shadow_offset,
                    x + node_w / 2 + shadow_offset,
                    y + node_h / 2 + shadow_offset,
                    corner_radius,
                    fill="#0b1b36",
                    outline="",
                    tags=(tag, "node_bg", "node"),
                )
                draw_rounded_panel(
                    x - node_w / 2,
                    y - node_h / 2,
                    x + node_w / 2,
                    y + node_h / 2,
                    corner_radius,
                    fill="#123567",
                    outline="#1f4a85",
                    width=max(1, int(1 * scale)),
                    tags=(tag, "node_bg", "node"),
                )
            else:
                if self.postit_base:
                    ow, oh = self.postit_base.size
                    if is_collapsed:
                        node_w, node_h = int(min_w), int(min_h)
                    else:
                        sf = max(min_w / ow, min_h / oh)
                        node_w, node_h = int(ow * sf), int(oh * sf)
                    bg_img = self.postit_base.resize((node_w, node_h), Image.Resampling.LANCZOS)
                    bg_photo = ImageTk.PhotoImage(bg_img, master=self.canvas)
                    self.node_holder_images[tag] = bg_photo
                    self.canvas.create_image(
                        x, y,
                        image=bg_photo,
                        anchor="center",
                        tags=(tag, "node_bg", "node")
                    )
                else:
                    node_w, node_h = min_w, min_h

            # ── 2) Draw the thumbtack pin ────────────────────────────
            if node_style == "postit" and self.pin_image:
                self.canvas.create_image(
                    x,
                    y - node_h // 2 - int(8 * scale) - 5,
                    image=self.pin_image,
                    anchor="n",
                    tags=(tag, "node_fg", "node")
                )

            # ── 3) Draw the portrait ─────────────────────────────────
            current_y = y - node_h // 2 + PAD
            if portrait_img:
                self.canvas.create_image(
                    x, current_y,
                    image=portrait_img,
                    anchor="n",
                    tags=(tag, "node_fg", "node")
                )
                current_y += p_h + GAP

            # ── 4) Draw the wrapped title ────────────────────────────
            if title_h > 0:
                title_id = self.canvas.create_text(
                    x, current_y,
                    text=title_text,
                    font=title_font,
                    fill=title_color,
                    width=wrap_width,
                    anchor="n",
                    justify="center",
                    tags=(tag, "node_fg", "node")
                )
                bbox = self.canvas.bbox(title_id)
                actual_h = (bbox[3] - bbox[1]) if bbox else title_h
                current_y += actual_h + (GAP if body_h > 0 else 0)

            # ── 5) Draw body text ────────────────────────────────────
            if body_h > 0:
                self.canvas.create_text(
                    x, current_y,
                    text=body_text,
                    font=body_font,
                    fill=body_color,
                    width=wrap_width,
                    anchor="n",
                    justify="center",
                    tags=(tag, "node_fg", "node")
                )

            # ── 6) Draw collapse/expand toggle ───────────────────────
            toggle_radius = max(4, int(8 * scale))
            toggle_margin = max(2, int(6 * scale))
            toggle_x = x + node_w / 2 + toggle_radius - toggle_margin
            toggle_y = y - node_h / 2 + toggle_radius + toggle_margin
            toggle_symbol = "+" if is_collapsed else "−"
            self.canvas.create_oval(
                toggle_x - toggle_radius,
                toggle_y - toggle_radius,
                toggle_x + toggle_radius,
                toggle_y + toggle_radius,
                fill="#2B2B2B" if node_style != "modern" else "#0f2c57",
                outline="#1B1B1B" if node_style != "modern" else "#1f4a85",
                tags=(tag, "node_fg", "node", "collapse_toggle")
            )
            self.canvas.create_text(
                toggle_x,
                toggle_y,
                text=toggle_symbol,
                font=("Arial", max(1, int(10 * scale)), "bold"),
                fill="white" if node_style != "modern" else "#f0f4ff",
                tags=(tag, "node_fg", "node", "collapse_toggle")
            )

            # ── 7) Store bounding box for links ──────────────────────
            self.node_bboxes[tag] = (
                x - node_w / 2, y - node_h / 2,
                x + node_w / 2, y + node_h / 2
            )

            # ── 8) Layer foreground above background ────────────────
            self.canvas.tag_raise("node_fg", "node_bg")

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_all_links
    # Iterates over all links in the graph and draws them, then lowers link elements behind nodes.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_all_links(self, links):
        for link in links:
            self.draw_one_link(link)
        self.canvas.tag_lower("link")

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_one_link
    # Draws a single link between two nodes, including its arrowheads (if any) and text.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_one_link(self, link):
        tag1 = link.get("node1_tag")
        tag2 = link.get("node2_tag")
        x1, y1 = self.node_positions.get(tag1, (0, 0))
        x2, y2 = self.node_positions.get(tag2, (0, 0))
        start_x, start_y = self._get_edge_point(tag1, x2, y2)
        end_x, end_y = self._get_edge_point(tag2, x1, y1)

        link_color, line_width = self._get_link_style(link)
        line_id = self.canvas.create_line(
            start_x,
            start_y,
            end_x,
            end_y,
            fill=link_color,
            width=line_width,
            tags=("link",),
        )
        arrow_mode = link.get("arrow_mode", "end")

        arrow_ids = []
        if arrow_mode in ("start", "both"):
            arrow_ids.append(self.draw_arrowhead(tag1, x2, y2, link_color))
        if arrow_mode in ("end", "both"):
            arrow_ids.append(self.draw_arrowhead(tag2, x1, y1, link_color))

        mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
        scale = self.canvas_scale
        font_size = max(1, int(10 * scale))

        text_id = self.canvas.create_text(
            mid_x, mid_y,
            text=link["text"],
            fill="white",
            font=("Arial", font_size, "bold"),
            tags=("link_text",)
        )

        # Store Canvas IDs clearly linked by node tags
        key = (tag1, tag2)
        self.link_canvas_ids[key] = {
            "line": line_id,
            "arrows": arrow_ids,
            "text": text_id
        }


    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: _get_edge_point
    # Returns the point where a link should touch the edge of a node's bounding box.
    # ─────────────────────────────────────────────────────────────────────────
    def _get_edge_point(self, node_tag, target_x, target_y):
        center_x, center_y = self.node_positions.get(node_tag, (0, 0))
        bbox = self.node_bboxes.get(node_tag)
        if not bbox:
            return center_x, center_y
        left, top, right, bottom = bbox
        half_w = (right - left) / 2
        half_h = (bottom - top) / 2
        dx = target_x - center_x
        dy = target_y - center_y
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return center_x, center_y
        if abs(dx) < 1e-6:
            scale = half_h / max(abs(dy), 1e-6)
        elif abs(dy) < 1e-6:
            scale = half_w / max(abs(dx), 1e-6)
        else:
            scale = min(half_w / abs(dx), half_h / abs(dy))
        return center_x + dx * scale, center_y + dy * scale

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_arrowhead
    # Draws a triangular arrowhead near a node, offset outside the node's bounding box.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_arrowhead(self, node_tag, target_x, target_y, color):
        arrow_length = 16
        arrow_width = 18
        arrow_apex_x, arrow_apex_y = self._get_edge_point(node_tag, target_x, target_y)
        angle = math.atan2(arrow_apex_y - target_y, arrow_apex_x - target_x)
        base_x = arrow_apex_x - arrow_length * math.cos(angle)
        base_y = arrow_apex_y - arrow_length * math.sin(angle)
        perp_x = -math.sin(angle)
        perp_y = math.cos(angle)
        left_x = base_x + (arrow_width / 2) * perp_x
        left_y = base_y + (arrow_width / 2) * perp_y
        right_x = base_x - (arrow_width / 2) * perp_x
        right_y = base_y - (arrow_width / 2) * perp_y

        # RETURN the polygon ID so it can be deleted later
        return self.canvas.create_polygon(
            arrow_apex_x, arrow_apex_y,
            left_x, left_y,
            right_x, right_y,
            fill=color,
            outline="",
            tags=("link", "arrowhead")
    )


    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: load_graph
    # Loads a graph from a JSON file, rebuilds node positions, and sets default values.
    # ─────────────────────────────────────────────────────────────────────────
    def load_graph(self, path=None):
        # ── 0) Clear existing canvas items (keep only background) ─────────────────
        for item in self.canvas.find_all():
            if "background" not in self.canvas.gettags(item):
                self.canvas.delete(item)
        # Reset internal state
        self.node_positions.clear()
        self.node_bboxes.clear()
        self.node_images.clear()
        self.node_holder_images.clear()
        self.link_canvas_ids.clear()
        self.shapes.clear()

        # ── 1) Prompt for file if needed and load JSON ───────────────────────────
        if not path:
            path = self.graph_path
            if not os.path.exists(path):
                path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
                if not path:
                    return
        self.graph_path = path
        with open(path, 'r', encoding='utf-8') as f:
            self.graph = json.load(f)
        self.graph.setdefault("shapes", [])
        ensure_graph_tabs(self.graph)

        # ── 2) Ensure every node dict has its own unique `tag` ────────────────────
        seen = set()
        for node in self.graph["nodes"]:
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
            # if JSON already had a tag and it's unused, keep it
            tag = node.get("tag", base)
            if tag in seen:
                # collide: generate a new one
                i = 1
                while f"{base}_{i}" in seen:
                    i += 1
                tag = f"{base}_{i}"
            node["tag"] = tag
            seen.add(tag)

        # ── 3) Rebuild node_positions from those tags ──────────────────────────────
        self.node_positions = {
            node["tag"]: (node["x"], node["y"])
            for node in self.graph["nodes"]
        }

        # ── 4) Fill in any defaults for color, arrow_mode, etc. ───────────────────
        for node in self.graph["nodes"]:
            node.setdefault("color", "#1D3572")
            node.setdefault("collapsed", True)
        if self.graph["nodes"]:
            self.nodes_collapsed = all(node.get("collapsed", True) for node in self.graph["nodes"])
        else:
            self.nodes_collapsed = True
        for link in self.graph["links"]:
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

        self._refresh_entity_records("npc")
        self._refresh_entity_records("pc")
        for link in list(self.graph.get("links", [])):
            self._persist_link_to_entities(link)
        self._merge_links_from_entities()

        # ── 5) Rebuild shapes dict & counter ─────────────────────────────────────
        shapes_sorted = sorted(self.graph["shapes"], key=lambda s: s.get("z", 0))
        for shape in shapes_sorted:
            self.shapes[shape["tag"]] = shape
        # update shape_counter so new shapes get unique tags
        max_i = 0
        for shape in self.graph["shapes"]:
            parts = shape["tag"].split("_")
            if parts[-1].isdigit():
                max_i = max(max_i, int(parts[-1]))
        self.shape_counter = max_i + 1

        # ── 6) Cache original positions for zoom/undo resets ─────────────────────
        self.original_positions = dict(self.node_positions)
        self.original_shape_positions = {
            sh["tag"]: (sh["x"], sh["y"])
            for sh in self.graph["shapes"]
        }

        # ── 7) Finally redraw ────────────────────────────────────────────────────
        self._refresh_tab_selector()
        self.draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: change_node_color
    # Changes the color of the currently selected node, updating both the canvas and the graph data.
    # ─────────────────────────────────────────────────────────────────────────
    def change_node_color(self, color):
        if self.selected_node:
            rect_id = self.node_rectangles[self.selected_node]
            self.canvas.itemconfig(rect_id, fill=color)
            for node in self.graph["nodes"]:
                if node.get("tag") == self.selected_node:
                    node["color"] = color
                    break
            self._autosave_graph()

    def change_shape_color(self, tag, color):
        self.canvas.itemconfig(tag, fill=color)
        shape = self.shapes.get(tag)
        if shape:
            shape["color"] = color
            self._autosave_graph()

    def show_shape_menu(self, x, y, shape_tag):
        shape_menu = Menu(self.canvas, tearoff=0)

        # Color submenu
        color_menu = Menu(shape_menu, tearoff=0)
        COLORS = [
            "red", "green", "blue", "yellow", "purple",
            "orange", "pink", "cyan", "magenta", "lightgray"
        ]
        for color in COLORS:
            color_menu.add_command(
                label=color,
                command=lambda c=color: self.change_shape_color(shape_tag, c)
            )

         # Add a Resize option
        shape_menu.add_cascade(label="Change Color", menu=color_menu)
        shape_menu.add_separator()
        shape_menu.add_command(label="Change shape size", command=lambda: self.activate_resize_mode(shape_tag))
        shape_menu.add_separator()
        shape_menu.add_command(label="Bring to Front", command=lambda: self.bring_to_front(shape_tag))
        shape_menu.add_command(label="Send to Back", command=lambda tag=shape_tag: self.send_to_back(tag))  
        shape_menu.add_separator()
        shape_menu.add_command(label="Delete Shape", command=lambda: self.delete_shape(shape_tag))
        shape_menu.post(int(x), int(y))

    def bring_to_front(self, shape_tag):
        # Raise the shape on the canvas.
        self.canvas.tag_raise(shape_tag)
        shape = self.shapes.get(shape_tag)
        if shape:
            # Set the shape's z property to a value higher than all others.
            max_z = max((s.get("z", 0) for s in self.shapes.values()), default=0)
            shape["z"] = max_z + 1
            # Update the order in the graph's shapes list.
            self.graph["shapes"].sort(key=lambda s: s.get("z", 0))
            self._autosave_graph()

    def send_to_back(self, tag=None):
        tag = tag or self.selected_shape
        if not tag:
            return
        background_exists = bool(self.canvas.find_withtag("background"))
        if background_exists:
            self.canvas.tag_raise(tag, "background")
        else:
            self.canvas.tag_lower(tag)
        if self.canvas.find_withtag("link"):
            self.canvas.tag_lower(tag, "link")
        self._autosave_graph()

    def activate_resize_mode(self, shape_tag):
        shape = self.shapes.get(shape_tag)
        if not shape:
            return

        # Calculate bottom-right corner (if that’s your chosen anchor).
        x, y, w, h = shape["x"], shape["y"], shape["w"], shape["h"]
        corner_x = x + w // 2
        corner_y = y + h // 2

        handle_size = 10
        handle_id = self.canvas.create_rectangle(
            corner_x - handle_size // 2, corner_y - handle_size // 2,
            corner_x + handle_size // 2, corner_y + handle_size // 2,
            fill="gray", tags=("resize_handle", shape_tag)
        )

        # Ensure the handle is on top
        self.canvas.tag_raise(handle_id)

        # Bind events to the handle
        self.canvas.tag_bind(handle_id, "<Button-1>", self.start_resizing, add="+")
        self.canvas.tag_bind(handle_id, "<B1-Motion>", self.do_resizing, add="+")
        self.canvas.tag_bind(handle_id, "<ButtonRelease-1>", self.end_resizing, add="+")

    def start_resizing(self, event):
        # Retrieve the shape tag from the current item.
        self.resizing_shape_tag = self.canvas.gettags("current")[1]  # second tag is shape_tag
        shape = self.shapes.get(self.resizing_shape_tag)
        if not shape:
            return
        # Store the shape's center as a fixed anchor.
        self.resize_center = (shape["x"], shape["y"])
        # Record the starting mouse position (if needed for reference)
        self.resize_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.original_width = shape["w"]
        self.original_height = shape["h"]

    def do_resizing(self, event):
        if not self.resizing_shape_tag:
            return
        shape = self.shapes.get(self.resizing_shape_tag)
        if not shape:
            return
        # Use the stored center as the anchor.
        cx, cy = self.resize_center
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        # Calculate new dimensions relative to the fixed center.
        new_width = max(10, 2 * (current_x - cx))
        new_height = max(10, 2 * (current_y - cy))
        shape["w"] = new_width
        shape["h"] = new_height

        # Recompute the bounding box so the center remains unchanged.
        left   = cx - new_width / 2
        top    = cy - new_height / 2
        right  = cx + new_width / 2
        bottom = cy + new_height / 2

        # Update the canvas coordinates for the shape.
        self.canvas.coords(shape["canvas_id"], left, top, right, bottom)

        # Move the resize handle to the new bottom-right corner.
        handle_id = shape.get("resize_handle")
        if handle_id:
            self.canvas.coords(handle_id,
                            right - 5, bottom - 5,
                            right + 5, bottom + 5)

    def end_resizing(self, event):
        # Clean up the resize mode; remove the handle.
        shape = self.shapes.get(self.resizing_shape_tag)
        if shape and "resize_handle" in shape:
            self.canvas.delete(shape["resize_handle"])
            del shape["resize_handle"]
        self.resizing_shape_tag = None
        self.resize_start = None
        self.resize_center = None
        self._autosave_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: distance_point_to_line
    # Calculates the distance from a point to a given line segment.
    # ─────────────────────────────────────────────────────────────────────────
    def distance_point_to_line(self, px, py, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        return math.hypot(px - nearest_x, py - nearest_y)

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: get_link_by_position
    # Returns the link that is within a threshold distance from the given (x, y) point.
    # ─────────────────────────────────────────────────────────────────────────
    def get_link_by_position(self, x, y):
        threshold = 50  # Threshold for hit-testing
        for link in self.graph["links"]:
            tag1 = link.get("node1_tag")
            tag2 = link.get("node2_tag")
            x1, y1 = self.node_positions.get(tag1, (0, 0))
            x2, y2 = self.node_positions.get(tag2, (0, 0))
            start_x, start_y = self._get_edge_point(tag1, x2, y2)
            end_x, end_y = self._get_edge_point(tag2, x1, y1)
            distance = self.distance_point_to_line(x, y, start_x, start_y, end_x, end_y)
            if distance < threshold:
                return link
        return None


    def add_shape(self, shape_type):
        x, y = 200, 200
        width, height = 120, 80
        active_tab = get_active_tab(self.graph)
        tab_id = active_tab.get("id") if active_tab else None
        tag = f"shape_{self.shape_counter}"
        self.shape_counter += 1
        shape = {
            "type": shape_type,
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "color": "lightgray",
            "tag": tag,
            "tab_id": tab_id,
        }
        self.graph["shapes"].append(shape)
        self.shapes[tag] = shape
        self.draw_shape(shape)
        self._autosave_graph()

    def draw_shape(self, shape):
        scale = self.canvas_scale
        x, y = shape["x"], shape["y"]
        w = int(shape["w"] * scale)
        h = int(shape["h"] * scale)

        left = x - w // 2
        top = y - h // 2
        right = x + w // 2
        bottom = y + h // 2
        tag = shape["tag"]

        if shape["type"] == "rectangle":
            shape_id = self.canvas.create_rectangle(
                left, top, right, bottom,
                fill=shape["color"],
                tags=(tag, "shape")
            )
        else:  # oval
            shape_id = self.canvas.create_oval(
                left, top, right, bottom,
                fill=shape["color"],
                tags=(tag, "shape")
            )

        shape["canvas_id"] = shape_id

    def draw_all_shapes(self):
        # Only draw shapes for the active tab (unless tab_id is missing).
        active_tab = get_active_tab(self.graph)
        active_id = active_tab.get("id") if active_tab else None
        self.shapes = {}
        shapes_sorted = sorted(self.graph.get("shapes", []), key=lambda s: s.get("z", 0))
        for shape in shapes_sorted:
            tab_id = shape.get("tab_id")
            if tab_id and active_id and tab_id != active_id:
                continue
            self.shapes[shape["tag"]] = shape
            self.draw_shape(shape)

    def _autosave_graph(self):
        self.save_graph(show_message=False)

    def save_graph(self, path=None, show_message=True):
        if not path:
            path = self.graph_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ensure_graph_tabs(self.graph)

        # 2) Update each node entry with its unique tag and current x,y
        for node in self.graph["nodes"]:
            tag = node.get("tag")
            # fallback to name‐based tag if somehow missing
            if not tag:
                entity_type = node.get("entity_type", "npc")
                entity_name = node.get("entity_name", "")
                tag = f"{entity_type}_{entity_name.replace(' ', '_')}"
                node["tag"] = tag

            # Pull the live position from self.node_positions
            pos = self.node_positions.get(tag)
            if pos:
                node["x"], node["y"] = pos
            else:
                # if for some reason it's missing, leave whatever was there
                pass

        for link in self.graph.get("links", []):
            link.setdefault("arrow_mode", "both")
        for shape in self.graph.get("shapes", []):
            shape.pop("canvas_id", None)
            shape.pop("resize_handle", None)

        # 3) Write out the full graph dict
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.graph, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")
            return
        if show_message:
            messagebox.showinfo("Saved", f"Graph saved to:\n{path}")

    def load_portrait_scaled(self, portrait_path, node_tag, scale=1.0):
        if portrait_path and not os.path.isabs(portrait_path):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
            if os.path.exists(candidate):
                portrait_path = candidate
        if not portrait_path or not os.path.exists(portrait_path):
            return None, (0, 0)
        try:
            img = Image.open(portrait_path)
            size = int(MAX_PORTRAIT_SIZE[0] * scale), int(MAX_PORTRAIT_SIZE[1] * scale)
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(size, resample_method)
            portrait_image = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[node_tag] = portrait_image
            return portrait_image, img.size
        except Exception as e:
            print(f"Error loading portrait for {node_tag}: {e}")
            return None, (0, 0)

    def _get_visible_graph_data(self):
        ensure_graph_tabs(self.graph)
        self._sync_active_tab_selection()
        active_tab = get_active_tab(self.graph)
        return filter_graph_for_tab(self.graph, active_tab)

    def _sync_active_tab_selection(self):
        if not self.tab_selector_var:
            return
        selected_name = (self.tab_selector_var.get() or "").strip()
        if not selected_name:
            return
        tab_id = self.tab_id_by_name.get(selected_name)
        if not tab_id:
            for tab in self.graph.get("tabs", []):
                if tab.get("name") == selected_name:
                    tab_id = tab.get("id")
                    break
        if tab_id:
            set_active_tab(self.graph, tab_id)

    def draw_graph(self):
        #self.canvas.delete("shape")
        #self.canvas.delete("link")
        #self.canvas.delete("link_text")
        # ── 1) Remove everything except the scene flow background ──
        #    we keep only items tagged “background”
        if self.background_style == "corkboard":
            self._apply_corkboard_background()
        else:
            self._apply_scene_flow_background()
        for item in self.canvas.find_all():
            if "background" not in self.canvas.gettags(item):
                self.canvas.delete(item)
        self.node_bboxes = {}
        self.draw_all_shapes()
        visible_nodes, visible_links = self._get_visible_graph_data()
        self.draw_nodes(visible_nodes)
        self.draw_all_links(visible_links)
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            padding = 50
            self.canvas.configure(scrollregion=(
                bbox[0] - padding, bbox[1] - padding,
                bbox[2] + padding, bbox[3] + padding
            ))
        # Check if there are any "link" items before using them as reference.
        # bring links above the background
        background_exists = bool(self.canvas.find_withtag("background"))
        if self.canvas.find_withtag("link"):
            if background_exists:
                self.canvas.tag_raise("link", "background")
            else:
                self.canvas.tag_raise("link")
        # then make sure nodes (post-its) are on top of everything
        if self.canvas.find_withtag("node"):
            self.canvas.tag_raise("node")
        # finally keep shapes just above background but below links/nodes
        if self.canvas.find_withtag("shape"):
            if background_exists:
                self.canvas.tag_raise("shape", "background")
            else:
                self.canvas.tag_raise("shape")

    def _get_link_style(self, link):
        is_selected = bool(self.selected_link and self._link_matches(link, self.selected_link))
        if is_selected:
            return "#5bb8ff", 3
        return "#2f4c6f", 2


    def start_drag(self, event):
        # Convert mouse coords to canvas coords
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        # Reset any previous selection
        self.selected_node = None
        self.selected_shape = None
        self.drag_start = None

        # Find all items under the cursor
        items = list(self.canvas.find_overlapping(x, y, x, y))
        # Iterate in reverse so the topmost items get priority
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            # First check for a node tag
            for tag in tags:
                if self._is_node_tag(tag):
                    self.selected_node = tag
                    break
            if self.selected_node:
                break
            # Then check for a shape tag
            for tag in tags:
                if tag.startswith("shape_"):
                    self.selected_shape = tag
                    break
            if self.selected_shape:
                break

        # If we found something, prepare for dragging
        active_tag = self.selected_node or self.selected_shape
        if active_tag:
            self.selected_items = self.canvas.find_withtag(active_tag)
            self.drag_start = (x, y)
        else:
            self.selected_items = []

    def on_drag(self, event):
        if not (self.selected_node or self.selected_shape) or not self.drag_start:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        for item in self.selected_items:
            self.canvas.move(item, dx, dy)
        if self.selected_node:
            old_x, old_y = self.node_positions[self.selected_node]
            self.node_positions[self.selected_node] = (old_x + dx, old_y + dy)
            self.update_links_positions_for_node(self.selected_node)
        if self.selected_shape:
            shape = self.shapes[self.selected_shape]
            shape["x"] += dx
            shape["y"] += dy
        self.drag_start = (x, y)

    def end_drag(self, event):
        did_drag = bool(self.selected_node or self.selected_shape)
        self.selected_node = None
        self.selected_shape = None
        self.selected_items = []
        self.drag_start = None
        if did_drag:
            self._autosave_graph()
