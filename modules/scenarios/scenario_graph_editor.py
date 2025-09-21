import json
import math
import customtkinter as ctk
import tkinter.font as tkFont
import re
import os
import ctypes
from ctypes import wintypes
#import logging
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk, Menu
from PIL import Image, ImageTk

from modules.helpers.template_loader import load_template
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.entity_detail_factory import create_entity_detail_frame, open_entity_window
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.text_helpers import format_longtext
from modules.ui.image_viewer import show_portrait
from modules.helpers.template_loader import load_template
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

# Global constants
PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (128, 128)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
#logging.basicConfig(level=logging.DEBUG)


def clean_longtext(data, max_length=2000):
    # First, get the plain text using your existing helper.
    text = format_longtext(data, max_length)
    # Remove curly braces.
    text = re.sub(r'[{}]', '', text)
    # Remove backslash control words (simple approach).
    text = re.sub(r'\\[a-zA-Z]+\s?', '', text)
    return text.strip()

class ScenarioGraphEditor(ctk.CTkFrame):
    def __init__(self, master,
                scenario_wrapper: GenericModelWrapper,
                npc_wrapper: GenericModelWrapper,
                creature_wrapper: GenericModelWrapper,
                place_wrapper: GenericModelWrapper,
                *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.scenario_wrapper = scenario_wrapper
        self.npc_wrapper = npc_wrapper
        self.creature_wrapper = creature_wrapper
        self.place_wrapper = place_wrapper
        self.node_holder_images = {}    # ← keep PhotoImage refs here
        self.node_bboxes = {}
        self.node_images = {}  # Prevent garbage collection of PhotoImage objects
        self.overlay_images={}
        # Preload NPC, Creature and Place data for quick lookup.
        self.npcs = {npc["Name"]: npc for npc in self.npc_wrapper.load_items()}
        self.creatures = {creature["Name"]: creature for creature in self.creature_wrapper.load_items()}
        self.places = {pl["Name"]: pl for pl in self.place_wrapper.load_items()}

        self.scenario = None
        self.canvas_scale = 1.0
        self.zoom_factor = 1.1
        self.type_icons = {
            "npc":      self.load_icon("assets/npc_icon.png",      32, 0.6),
            "place":    self.load_icon("assets/places_icon.png",    32, 0.6),
            "scenario": self.load_icon("assets/gm_screen_icon.png", 32, 0.6),
            "creature": self.load_icon("assets/creature_icon.png", 32, 0.6),
            "scene":    self.load_icon("assets/scenario_icon.png", 32, 0.6)
        }
        
        # Graph structure.
        self.graph = {"nodes": [], "links": []}
        self.node_positions = {}   # Maps node_tag -> (x, y)
        self.node_rectangles = {}  # Maps node_tag -> rectangle_id
        self.selected_node = None
        self.selected_items = []
        self.drag_start = None
        self.original_positions = {}
        self.canvas_link_items = {}
        self.scene_flow_scenes = []
        self.scene_flow_scene_lookup = {}

        self.init_toolbar()
        postit_path = "assets/images/post-it.png"
        pin_path = "assets/images/thumbtack.png"
             
        # Create canvas with scrollbars.
        self.canvas_frame = ctk.CTkFrame(self)
        self.canvas_frame.pack(fill="both", expand=True)
        self.canvas = ctk.CTkCanvas(self.canvas_frame, bg="#2B2B2B", highlightthickness=0)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        VIRTUAL_WIDTH = 5000
        VIRTUAL_HEIGHT = 5000
        if os.path.exists(postit_path):
            img = Image.open(postit_path).convert("RGBA")
            self.postit_base = img

        if os.path.exists(pin_path):
            pin_img = Image.open(pin_path)
            self.pin_image = ImageTk.PhotoImage(pin_img.resize((32, 32), Image.Resampling.LANCZOS), master=self.canvas)
        # Load and display the background image at the top-left
        background_path = "assets/images/corkboard_bg.png"
       
        if os.path.exists(background_path):
            self.background_image = Image.open(background_path)

            # Resize the PIL image (e.g. 2x scale)
            zoom_factor = 2
            w=1920
            h=1080
            self.background_image = self.background_image.resize((w * zoom_factor, h * zoom_factor), Image.Resampling.LANCZOS)

            self.background_photo = ImageTk.PhotoImage(self.background_image, master=self.canvas)
            self.background_id = self.canvas.create_image(
                0, 0,
                image=self.background_photo,
                anchor="center",  # or "nw" if you want top-left alignment
                tags="background"
            )
            self.canvas.tag_lower("background")
           
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
       
        # Global mouse events.
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_y)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom)  # Windows
        self.canvas.bind("<Control-Button-4>", self._on_zoom)    # Linux scroll up
        self.canvas.bind("<Control-Button-5>", self._on_zoom)    # Linux scroll down
        self.canvas.bind("<Shift-Button-4>", self._on_mousewheel_x)
        self.canvas.bind("<Shift-Button-5>", self._on_mousewheel_x)
    
    def _on_zoom(self, event):
        if event.delta > 0 or event.num == 4:
            scale = self.zoom_factor
        else:
            scale = 1 / self.zoom_factor

        new_scale = self.canvas_scale * scale
        new_scale = max(0.5, min(new_scale, 2.5))  # Clamp zoom to reasonable range
        scale_change = new_scale / self.canvas_scale
        self.canvas_scale = new_scale

        # Use mouse pointer as anchor for better UX
        anchor_x = self.canvas.canvasx(event.x)
        anchor_y = self.canvas.canvasy(event.y)

        # Rescale all node positions
        for tag, (x, y) in self.node_positions.items():
            dx = x - anchor_x
            dy = y - anchor_y
            new_x = anchor_x + dx * scale_change
            new_y = anchor_y + dy * scale_change
            self.node_positions[tag] = (new_x, new_y)

            # Update x/y in the node data as well
            for node in self.graph["nodes"]:
                node_tag = f"{node['type']}_{node['name'].replace(' ', '_')}"
                if node_tag == tag:
                    node["x"], node["y"] = new_x, new_y
                    break

        self.draw_graph()

        # Optional: zoom font sizes, overlays, etc., here if you want to support them visually
    def reset_zoom(self):
        self.canvas_scale = 1.0

        # Restore original node positions
        for node in self.graph["nodes"]:
            tag = f"{node['type']}_{node['name'].replace(' ', '_')}"
            if tag in self.original_positions:
                x, y = self.original_positions[tag]
                node["x"] = x
                node["y"] = y

        # Rebuild node_positions from graph data
        self.node_positions = {
            f"{node['type']}_{node['name'].replace(' ', '_')}": (node["x"], node["y"])
            for node in self.graph["nodes"]
        }

        self.draw_graph()
    
    def init_toolbar(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Select Scenario", command=self.select_scenario).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Scenes Flow View", command=self.show_scene_flow).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Entity Overview", command=self.show_entity_view).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Save Graph", command=self.save_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Load Graph", command=self.load_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Reset Zoom", command=self.reset_zoom).pack(side="left", padx=5)


    def show_scene_flow(self):
        if not self.scenario:
            messagebox.showinfo("Select Scenario", "Please select a scenario first to build the scene flow view.")
            return
        self.load_scenario_scene_flow(self.scenario)

    def show_entity_view(self):
        if not self.scenario:
            messagebox.showinfo("Select Scenario", "Please select a scenario first to display its entity overview.")
            return
        self.load_scenario(self.scenario)


    def select_scenario(self):
        def on_scenario_selected(scenario_name):
            # Lookup the full pc dictionary using the pc wrapper.
            scenario_list = self.scenario_wrapper.load_items()
            selected_scenario = None
            for scenario in scenario_list:
                if scenario.get("Title") == scenario_name:
                    selected_scenario = scenario
                    break
            if not selected_scenario:
                messagebox.showerror("Error", f"scenario '{scenario_name}' not found.")
                return
            dialog.destroy()
            self.load_scenario(selected_scenario)

        scenario_template = load_template("scenarios")
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select scenario")
        dialog.geometry("1200x800")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        # The new GenericListSelectionView returns the pc name (string)
        selection_view = GenericListSelectionView(
            dialog,
            "scenarios",
            self.scenario_wrapper,
            scenario_template,
            on_select_callback=lambda et, scenario: on_scenario_selected(scenario)
        )
        selection_view.pack(fill="both", expand=True)
        dialog.wait_window()


    def display_portrait_window(self):
       #logging.debug("Entering display_portrait_window")
        if not self.selected_node or not (self.selected_node.startswith("npc_") or self.selected_node.startswith("creature_")):
            messagebox.showerror("Error", "No NPC or Creature selected.")
            return

        # Extract name after prefix. Note that creatures use "creature_" prefix.
        if self.selected_node.startswith("npc_"):
            name_key = self.selected_node.replace("npc_", "").replace("_", " ")
            data_source = self.npcs
        else:
            name_key = self.selected_node.replace("creature_", "").replace("_", " ")
            data_source = self.creatures

       #logging.debug(f"Extracted name: {name_key}")
        entity_data = data_source.get(name_key)
        if not entity_data:
            messagebox.showerror("Error", f"Entity '{name_key}' not found.")
            return

        portrait_path = entity_data.get("Portrait", "")
        if not portrait_path or not os.path.exists(portrait_path):
            messagebox.showerror("Error", "No valid portrait found for this entity.")
            return
        show_portrait(portrait_path, name_key)
        

    def load_scenario(self, scenario):
        # Use full text; no truncation—wrapping will be handled by canvas.
        summary = scenario.get("Summary", "")
        summary = clean_longtext(summary, max_length=5000)
        # Extract secret for the scenario node.
        secret = scenario.get("Secret", "")
        secret = clean_longtext(secret, max_length=5000)
        self.scenario = scenario
        self.graph = {"nodes": [], "links": []}
        self.node_positions.clear()

        center_x, center_y = 400, 300
        scenario_title = scenario.get("Title", "No Title")
        scenario_tag = f"scenario_{scenario_title.replace(' ', '_')}"
        self.graph["nodes"].append({
            "type": "scenario",
            "name": scenario_title,
            "x": center_x,
            "y": center_y,
            "color": "darkolivegreen",
            "data": {**scenario, "Summary": summary, "Secret": secret}
        })
        self.node_positions[scenario_tag] = (center_x, center_y)

        # NPC nodes
        npcs_list = scenario.get("NPCs", [])
        npcs_count = len(npcs_list)
        if npcs_count > 0:
            arc_start_npcs = 30
            arc_end_npcs = 150
            offset_npcs = 350

            for i, npc_name in enumerate(npcs_list):
                if npc_name not in self.npcs:
                    continue
                angle_deg = (arc_start_npcs if npcs_count == 1
                            else arc_start_npcs + i * (arc_end_npcs - arc_start_npcs) / (npcs_count - 1))
                angle_rad = math.radians(angle_deg)
                x = center_x + offset_npcs * math.cos(angle_rad)
                y = center_y + offset_npcs * math.sin(angle_rad)
                npc_data = self.npcs[npc_name]
                secret = npc_data.get("Secret", "")
                secret = clean_longtext(secret, max_length=5000)
                npc_data["Secret"] = secret
                traits = npc_data.get("Traits", "")
                traits = clean_longtext(traits, max_length=5000)
                npc_data["Traits"] = traits
                npc_tag = f"npc_{npc_name.replace(' ', '_')}"
                self.graph["nodes"].append({
                    "type": "npc",
                    "name": npc_name,
                    "x": x,
                    "y": y,
                    "color": "darkslateblue",
                    "data": npc_data
                })
                self.node_positions[npc_tag] = (x, y)
                self.graph["links"].append({
                    "from": scenario_tag,
                    "to": npc_tag,
                    "text": ""
                })

        # Place nodes
        places_list = scenario.get("Places", [])
        places_count = len(places_list)
        if places_count > 0:
            arc_start_places = 210
            arc_end_places = 330
            offset_places = 350

            for j, place_name in enumerate(places_list):
                if place_name not in self.places:
                    continue
                angle_deg = (arc_start_places if places_count == 1
                            else arc_start_places + j * (arc_end_places - arc_start_places) / (places_count - 1))
                angle_rad = math.radians(angle_deg)
                x = center_x + offset_places * math.cos(angle_rad)
                y = center_y + offset_places * math.sin(angle_rad)
                place_data = self.places[place_name]
                pd = place_data.get("Description", "")
                pd = clean_longtext(pd, max_length=5000)
                place_data["Description"] = pd
                # Add secret field processing for places
                secret = place_data.get("Secret", "")
                secret = clean_longtext(secret, max_length=5000)
                place_data["Secret"] = secret
                place_tag = f"place_{place_name.replace(' ', '_')}"
                self.graph["nodes"].append({
                    "type": "place",
                    "name": place_name,
                    "x": x,
                    "y": y,
                    "color": "sienna",
                    "data": place_data
                })
                self.node_positions[place_tag] = (x, y)
                self.graph["links"].append({
                    "from": scenario_tag,
                    "to": place_tag,
                    "text": ""
                })

        # Creature nodes
        creatures_list = scenario.get("Creatures") or []
        creatures_count = len(creatures_list)
        if creatures_count > 0:
            # Define an arc for creatures (e.g. between 150° and 210°)
            arc_start_creatures = 150
            arc_end_creatures = 210
            offset_creatures = 350

            for k, creature_name in enumerate(creatures_list):
                if creature_name not in self.creatures:
                    continue
                angle_deg = (arc_start_creatures if creatures_count == 1
                            else arc_start_creatures + k * (arc_end_creatures - arc_start_creatures) / (creatures_count - 1))
                angle_rad = math.radians(angle_deg)
                x = center_x + offset_creatures * math.cos(angle_rad)
                y = center_y + offset_creatures * math.sin(angle_rad)
                creature_data = self.creatures[creature_name]
                desc = creature_data.get("Description", "")
                desc = clean_longtext(desc, max_length=5000)
                creature_data["Description"] = desc
                # Add secret field processing for creatures
                weakness = creature_data.get("Weakness", "")
                weakness = clean_longtext(weakness, max_length=5000)
                creature_data["Weakness"] = weakness
                creature_tag = f"creature_{creature_name.replace(' ', '_')}"
                self.graph["nodes"].append({
                    "type": "creature",
                    "name": creature_name,
                    "x": x,
                    "y": y,
                    "color": "darkblue",
                    "data": creature_data
                })
                self.node_positions[creature_tag] = (x, y)
                self.graph["links"].append({
                    "from": scenario_tag,
                    "to": creature_tag,
                    "text": ""
                })

        self.draw_graph()
        self.canvas.update_idletasks()

        # Center view on scenario node (or graph content center)
        if scenario_tag in self.node_positions:
            x, y = self.node_positions[scenario_tag]

            # Get current scrollregion
            scroll_x0, scroll_y0, scroll_x1, scroll_y1 = self.canvas.bbox("all")
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Calculate scroll fractions (clamped between 0.0 and 1.0)
            scroll_x_frac = max(0.0, min(1.0, (x - canvas_width / 2 - scroll_x0) / (scroll_x1 - scroll_x0)))
            scroll_y_frac = max(0.0, min(1.0, (y - canvas_height / 2 - scroll_y0) / (scroll_y1 - scroll_y0)))

            self.canvas.xview_moveto(scroll_x_frac)
            self.canvas.yview_moveto(scroll_y_frac)

    def load_scenario_scene_flow(self, scenario=None):
        if scenario is not None:
            self.scenario = scenario
        scenario_data = self.scenario
        if not scenario_data:
            messagebox.showinfo("Select Scenario", "Please select a scenario first to build the scene flow view.")
            return

        scenes_raw = scenario_data.get("Scenes")
        scenes_list = self._coerce_scene_list(scenes_raw)
        if not scenes_list:
            messagebox.showinfo("Scene Flow", "This scenario does not contain any scenes to display.")
            return

        scenario_npcs = self._dedupe_preserve_order(self._to_list(scenario_data.get("NPCs")))
        scenario_creatures = self._dedupe_preserve_order(self._to_list(scenario_data.get("Creatures")))
        scenario_places = self._dedupe_preserve_order(self._to_list(scenario_data.get("Places")))

        normalized_scenes = []
        for idx, entry in enumerate(scenes_list):
            normalized = self._normalize_scene_entry(
                entry,
                idx,
                scenario_npcs,
                scenario_creatures,
                scenario_places
            )
            if normalized:
                normalized_scenes.append(normalized)

        if not normalized_scenes:
            messagebox.showinfo("Scene Flow", "No readable scenes were found for this scenario.")
            return

        self.graph = {"nodes": [], "links": []}
        self.node_positions.clear()
        self.scene_flow_scenes = normalized_scenes

        count = len(normalized_scenes)
        cols = min(4, max(1, int(math.ceil(math.sqrt(count)))))
        x_spacing = 360
        y_spacing = 320
        origin_x = 400
        origin_y = 260

        for idx, scene in enumerate(normalized_scenes):
            row = idx // cols
            col = idx % cols
            x = origin_x + (col - (cols - 1) / 2) * x_spacing
            y = origin_y + row * y_spacing

            display_name = scene.get("display_name") or f"Scene {idx + 1}"
            node_tag = f"scene_{display_name.replace(' ', '_')}"
            scene["tag"] = node_tag
            node_data = {
                "type": "scene",
                "name": display_name,
                "x": x,
                "y": y,
                "color": scene.get("color", "#d1a86d"),
                "data": {
                    "Text": scene.get("text", ""),
                    "Entities": scene.get("entities", [])
                }
            }
            self.graph["nodes"].append(node_data)
            self.node_positions[node_tag] = (x, y)

        lookup, index_lookup = self._build_scene_lookup(normalized_scenes)
        self.scene_flow_scene_lookup = {
            scene.get("tag"): scene for scene in normalized_scenes if scene.get("tag")
        }

        existing_links = set()
        tag_lookup = self.scene_flow_scene_lookup
        for scene in normalized_scenes:
            from_tag = scene.get("tag")
            if not from_tag:
                continue
            links = list(scene.get("links", []))
            if not links and scene.get("index", 0) < count - 1:
                next_scene = normalized_scenes[scene["index"] + 1]
                if next_scene.get("tag"):
                    links.append({"target_tag": next_scene["tag"], "text": "Continue"})

            for link in links:
                text = (link.get("text") or "").strip()
                if not text:
                    text = "Continue"

                target_tag = link.get("target_tag")
                if not target_tag:
                    target_index = link.get("target_index")
                    if isinstance(target_index, int):
                        target_tag = index_lookup.get(target_index)
                if not target_tag:
                    target_tag = self._resolve_scene_reference(link.get("target_key"), lookup, index_lookup)
                if not target_tag:
                    target_tag = self._resolve_scene_reference(link.get("target"), lookup, index_lookup)

                if not target_tag or target_tag == from_tag:
                    continue

                key = (from_tag, target_tag, text)
                if key in existing_links:
                    continue
                existing_links.add(key)
                target_scene = tag_lookup.get(target_tag)
                if target_scene and not isinstance(link.get("target_index"), int):
                    link["target_index"] = target_scene.get("index")
                link["target_tag"] = target_tag
                link["source_tag"] = from_tag
                link["source_scene_index"] = scene.get("index")
                if target_scene:
                    link["target_scene_index"] = target_scene.get("index")
                self.graph["links"].append({
                    "from": from_tag,
                    "to": target_tag,
                    "text": text,
                    "source_scene_index": scene.get("index"),
                    "target_scene_index": target_scene.get("index") if target_scene else None,
                    "link_data": link,
                })

        self.original_positions = dict(self.node_positions)
        self.canvas_scale = 1.0
        self.draw_graph()
        self.canvas.update_idletasks()

        bbox_all = self.canvas.bbox("all")
        if bbox_all:
            x0, y0, x1, y1 = bbox_all
            canvas_width = self.canvas.winfo_width() or 1
            canvas_height = self.canvas.winfo_height() or 1
            center_x = (x0 + x1) / 2
            center_y = (y0 + y1) / 2
            span_x = max(1, x1 - x0)
            span_y = max(1, y1 - y0)
            self.canvas.xview_moveto(max(0.0, min(1.0, (center_x - canvas_width / 2 - x0) / span_x)))
            self.canvas.yview_moveto(max(0.0, min(1.0, (center_y - canvas_height / 2 - y0) / span_y)))

    def _coerce_scene_list(self, scenes_raw):
        if not scenes_raw:
            return []
        if isinstance(scenes_raw, list):
            return scenes_raw
        if isinstance(scenes_raw, dict):
            if isinstance(scenes_raw.get("Scenes"), list):
                return scenes_raw["Scenes"]
            return [scenes_raw]
        if isinstance(scenes_raw, str):
            text = scenes_raw.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                if isinstance(parsed.get("Scenes"), list):
                    return parsed["Scenes"]
                return [parsed]
            blocks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]
            return blocks or [text]
        return [scenes_raw]

    def _normalize_scene_entry(self, entry, index, scenario_npcs, scenario_creatures, scenario_places):
        raw_text = ""
        if isinstance(entry, dict):
            text_fragments = []
            for key in ("Text", "text", "Description", "Summary", "Body", "Details", "Notes", "Gist", "Content"):
                value = entry.get(key)
                if isinstance(value, str):
                    text_fragments.append(value)
                elif isinstance(value, list):
                    text_fragments.extend(str(v) for v in value if v)
                elif isinstance(value, dict):
                    if isinstance(value.get("text"), str):
                        text_fragments.append(value.get("text"))
                    else:
                        text_fragments.extend(
                            str(v) for v in value.values() if isinstance(v, str)
                        )
            raw_text = "\n\n".join(fragment for fragment in text_fragments if str(fragment).strip())
            if not raw_text:
                alt = entry.get("text")
                if isinstance(alt, dict):
                    raw_text = alt.get("text", "")
                elif isinstance(alt, str):
                    raw_text = alt
        elif isinstance(entry, str):
            raw_text = entry
        else:
            raw_text = str(entry)

        cleaned_text = clean_longtext(raw_text, max_length=1600).strip()
        lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]

        title_text = ""
        if isinstance(entry, dict):
            for key in ("Title", "Scene", "Heading", "Name", "Label"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip():
                    title_text = val.strip()
                    break

        if not title_text and lines:
            title_text = lines[0]
            lines = lines[1:]
        title_text = self._clean_scene_title(title_text) if title_text else ""

        if lines:
            body_text = "\n".join(lines).strip()
        else:
            body_text = cleaned_text

        if len(body_text) > 1200:
            trimmed = body_text[:1200]
            cut = trimmed.rfind(" ")
            if cut > 900:
                trimmed = trimmed[:cut]
            body_text = trimmed.rstrip() + "..."

        if not title_text:
            title_text = f"Scene {index + 1}"

        npc_names = []
        creature_names = []
        place_names = []
        if isinstance(entry, dict):
            for field in ("NPCs", "InvolvedNPCs", "Participants", "Allies", "Characters"):
                npc_names.extend(self._to_list(entry.get(field)))
            for field in ("Creatures", "Monsters", "Enemies", "Foes", "Opponents", "Threats"):
                creature_names.extend(self._to_list(entry.get(field)))
            for field in ("Places", "Locations", "Site", "Setting", "Where", "Venue"):
                place_names.extend(self._to_list(entry.get(field)))

            entity_blob = entry.get("Entities") or entry.get("EntityRefs") or entry.get("Actors")
            if isinstance(entity_blob, list):
                for ent in entity_blob:
                    if isinstance(ent, dict):
                        ent_type = (ent.get("type") or ent.get("Type") or ent.get("category") or "").lower()
                        ent_name = ent.get("name") or ent.get("Name") or ent.get("title")
                        if ent_name:
                            if ent_type in ("npc", "character", "ally"):
                                npc_names.append(ent_name)
                            elif ent_type in ("creature", "monster", "enemy", "foe"):
                                creature_names.append(ent_name)
                            elif ent_type in ("place", "location", "site"):
                                place_names.append(ent_name)
                            else:
                                npc_names.append(ent_name)
                    elif isinstance(ent, str):
                        npc_names.append(ent)

        npc_names = self._dedupe_preserve_order(npc_names)
        creature_names = self._dedupe_preserve_order(creature_names)
        place_names = self._dedupe_preserve_order(place_names)

        search_text = f"{title_text}\n{body_text}".lower()
        if not npc_names:
            npc_names.extend(self._find_mentions(search_text, scenario_npcs))
        if not creature_names:
            creature_names.extend(self._find_mentions(search_text, scenario_creatures))
        if not place_names:
            place_names.extend(self._find_mentions(search_text, scenario_places))

        npc_names = self._dedupe_preserve_order(npc_names)
        creature_names = self._dedupe_preserve_order(creature_names)
        place_names = self._dedupe_preserve_order(place_names)

        entities = []
        seen_pairs = set()

        def add_entities(names, ent_type):
            for name in names:
                cleaned = str(name).strip()
                if not cleaned:
                    continue
                key = (ent_type, cleaned.lower())
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                record = self._lookup_entity_by_name(ent_type, cleaned)
                portrait = self._extract_entity_image(record, ent_type) if record else ""
                entities.append({
                    "type": ent_type,
                    "name": cleaned,
                    "portrait": portrait
                })

        add_entities(npc_names, "npc")
        add_entities(creature_names, "creature")
        add_entities(place_names, "place")

        raw_links = []
        if isinstance(entry, dict):
            for field in ("Links", "Transitions", "Choices", "Branches", "Paths", "Outcomes"):
                raw_links.extend(self._coerce_scene_links(entry.get(field)))
            for field in ("Next", "NextScene", "NextScenes", "LeadsTo", "OnSuccess", "OnFailure", "IfSuccess", "IfFailure"):
                raw_links.extend(self._coerce_scene_links(entry.get(field)))

        normalised_links = []
        seen_links = set()
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            target_value = item.get("target")
            text_value = item.get("text")
            if isinstance(target_value, dict):
                target_value = target_value.get("target") or target_value.get("Scene") or target_value.get("Next")
            text_clean = clean_longtext(str(text_value), max_length=160).strip() if text_value else ""
            target_index = None
            if isinstance(target_value, (int, float)):
                target_index = int(target_value)
            elif isinstance(target_value, str):
                stripped = target_value.strip()
                if stripped.isdigit():
                    target_index = int(stripped)
                else:
                    match = re.search(r"(scene|scène)\s*(\d+)", stripped, re.IGNORECASE)
                    if match:
                        target_index = int(match.group(2))
            key = (repr(target_value), text_clean)
            if key in seen_links:
                continue
            seen_links.add(key)
            normalised_links.append({
                "target": target_value,
                "target_key": target_value,
                "target_index": target_index,
                "text": text_clean
            })

        base_title = title_text.strip()
        if len(base_title) > 80:
            base_title = base_title[:77].rstrip() + "..."
        display_title = base_title or f"Scene {index + 1}"
        display_name = f"{index + 1}. {display_title}"
        if len(display_name) > 60:
            display_name = display_name[:57].rstrip() + "..."

        identifiers = set()
        identifiers.add(str(index + 1))
        identifiers.add(display_title)
        identifiers.add(display_name)
        identifiers.add(self._normalize_scene_identifier_key(display_title))
        identifiers.add(self._slugify_scene_identifier(display_title))
        if isinstance(entry, dict):
            for key_name in ("Id", "ID", "SceneId", "Key", "Slug", "Tag", "Reference"):
                value = entry.get(key_name)
                if value:
                    identifiers.add(str(value))
                    norm = self._normalize_scene_identifier_key(value)
                    if norm:
                        identifiers.add(norm)
                    slug = self._slugify_scene_identifier(value)
                    if slug:
                        identifiers.add(slug)

        identifiers = {ident for ident in identifiers if ident}

        return {
            "index": index,
            "display_name": display_name,
            "title": display_title,
            "text": body_text,
            "entities": entities,
            "links": normalised_links,
            "color": self._scene_color_from_entry(entry),
            "identifiers": identifiers,
            "source_entry": entry if isinstance(entry, dict) else None,
        }

    def _scene_color_from_entry(self, entry):
        if not isinstance(entry, dict):
            return "#d1a86d"
        type_value = entry.get("Type") or entry.get("type") or entry.get("Category") or entry.get("SceneType") or entry.get("Mood")
        if isinstance(type_value, str):
            lowered = type_value.lower()
            if any(token in lowered for token in ("combat", "battle", "fight", "skirmish")):
                return "#b96a55"
            if any(token in lowered for token in ("social", "role", "parley", "diplom")):
                return "#4f6fb5"
            if any(token in lowered for token in ("invest", "myster", "clue", "explor")):
                return "#c3973a"
            if any(token in lowered for token in ("travel", "chase", "journey", "pursuit")):
                return "#5e8f6b"
            if any(token in lowered for token in ("downtime", "rest", "interlude")):
                return "#8d7ac0"
        return "#d1a86d"

    def _clean_scene_title(self, text):
        if not text:
            return ""
        cleaned = str(text).strip()
        cleaned = re.sub(r"^[\u2022\-\*\s\t]+", "", cleaned)
        cleaned = re.sub(r"^(?:scene|scène|acte)\s*\d+\s*[:.\-]*\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^[^\w]+", "", cleaned)
        return cleaned.strip()

    def _to_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    name = item.get("Name") or item.get("Title") or item.get("name") or item.get("text")
                    if name:
                        result.append(str(name).strip())
                else:
                    item_str = str(item).strip()
                    if item_str:
                        result.append(item_str)
            return result
        if isinstance(value, (set, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, dict):
            collected = []
            for sub in value.values():
                collected.extend(self._to_list(sub))
            return collected
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if parsed is not None:
                return self._to_list(parsed)
            parts = [part.strip() for part in re.split(r"[,;\n]", text) if part.strip()]
            return parts or [text]
        return [str(value)]

    def _dedupe_preserve_order(self, values):
        result = []
        seen = set()
        for value in values or []:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _lookup_entity_by_name(self, entity_type, name):
        if not name:
            return None
        name_text = str(name).strip()
        if not name_text:
            return None
        pools = {
            "npc": self.npcs,
            "creature": self.creatures,
            "place": self.places,
        }
        collection = pools.get(entity_type)
        if not isinstance(collection, dict):
            return None
        if name_text in collection:
            return collection[name_text]
        lower = name_text.lower()
        for key, value in collection.items():
            if key.lower() == lower:
                return value
        return None

    def _find_mentions(self, text, candidates):
        if not text or not candidates:
            return []
        lower_text = text.lower()
        matches = []
        for candidate in candidates:
            if not candidate:
                continue
            candidate_text = str(candidate).strip()
            if not candidate_text:
                continue
            if candidate_text.lower() in lower_text:
                matches.append(candidate_text)
        return matches

    def _coerce_scene_links(self, value):
        links = []
        if value is None:
            return links
        if isinstance(value, list):
            for item in value:
                links.extend(self._coerce_scene_links(item))
            return links
        if isinstance(value, dict):
            target = None
            text = None
            for key in ("target", "Target", "to", "To", "scene", "Scene", "next", "Next", "id", "Id", "goto", "GoTo"):
                if key in value:
                    target = value[key]
                    break
            for key in ("text", "Text", "label", "Label", "description", "Description", "summary", "Summary", "choice", "Choice", "result", "Result", "outcome", "Outcome", "condition", "Condition"):
                if key in value:
                    text = value[key]
                    break
            if target is not None or text is not None:
                links.append({"target": target, "text": text})
            else:
                for key, sub in value.items():
                    sub_links = self._coerce_scene_links(sub)
                    if sub_links:
                        for link in sub_links:
                            if not link.get("text") and isinstance(key, str):
                                link["text"] = key
                        links.extend(sub_links)
                    else:
                        links.append({"target": sub, "text": key})
            return links
        if isinstance(value, (int, float)):
            links.append({"target": int(value), "text": ""})
            return links
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return links
            links.append({"target": text_value, "text": text_value})
            return links
        return links

    def _build_scene_lookup(self, scenes):
        lookup = {}
        index_lookup = {}
        for scene in scenes:
            tag = scene.get("tag")
            index = scene.get("index", 0)
            if tag:
                index_lookup[index] = tag
                index_lookup[index + 1] = tag
            for ident in scene.get("identifiers", []) or []:
                norm = self._normalize_scene_identifier_key(ident)
                if norm and norm not in lookup:
                    lookup[norm] = tag
                slug = self._slugify_scene_identifier(ident)
                if slug and slug not in lookup:
                    lookup[slug] = tag
        return lookup, index_lookup

    def _resolve_scene_reference(self, reference, lookup, index_lookup):
        if reference is None:
            return None
        if isinstance(reference, dict):
            for key in ("target", "Target", "Scene", "scene", "Next", "next", "Id", "id"):
                if key in reference:
                    resolved = self._resolve_scene_reference(reference[key], lookup, index_lookup)
                    if resolved:
                        return resolved
            return None
        if isinstance(reference, list):
            for item in reference:
                resolved = self._resolve_scene_reference(item, lookup, index_lookup)
                if resolved:
                    return resolved
            return None
        if isinstance(reference, (int, float)):
            return index_lookup.get(int(reference))
        if isinstance(reference, str):
            ref = reference.strip()
            if not ref:
                return None
            if ref.isdigit():
                target = index_lookup.get(int(ref))
                if target:
                    return target
            lowered = ref.lower()
            match = re.search(r"(scene|scène|acte)\s*(\d+)", lowered)
            if match:
                num = int(match.group(2))
                target = index_lookup.get(num)
                if target:
                    return target
            candidates = [ref, lowered]
            cleaned = re.sub(r"^(scene|scène|acte)\s*", "", lowered, flags=re.IGNORECASE).strip()
            if cleaned and cleaned != lowered:
                candidates.append(cleaned)
            if ":" in ref:
                prefix = ref.split(":", 1)[0].strip()
                if prefix:
                    candidates.append(prefix)
            for candidate in candidates:
                norm = self._normalize_scene_identifier_key(candidate)
                if norm and norm in lookup:
                    return lookup[norm]
                slug = self._slugify_scene_identifier(candidate)
                if slug and slug in lookup:
                    return lookup[slug]
        return None

    def _normalize_scene_identifier_key(self, value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(int(value))
        text = str(value).strip().lower()
        if not text:
            return ""
        text = text.replace("’", "'")
        text = re.sub(r"[\s_/]+", " ", text)
        return text

    def _slugify_scene_identifier(self, value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(int(value))
        text = str(value).lower().replace("’", "")
        slug = re.sub(r"[^a-z0-9]+", "-", text)
        return slug.strip('-')

    def draw_graph(self):
        self.canvas.delete("node")
        self.canvas.delete("link")
        self.node_rectangles.clear()
        self.draw_nodes()
        self.draw_links()
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            padding = 50
            self.canvas.configure(scrollregion=(
                bbox[0] - padding, bbox[1] - padding,
                bbox[2] + padding, bbox[3] + padding
            ))
        # Ensure proper layering
        if hasattr(self, "background_id"):
            self.canvas.tag_lower(self.background_id)

        self.canvas.tag_raise("link")  # Put links behind everything
        self.canvas.tag_raise("node")  # Bring nodes to the top

    def _extract_entity_image(self, record, entity_type):
        if not isinstance(record, dict):
            return ""
        priority_keys = ["Portrait", "portrait", "Image", "image", "TokenImage", "tokenImage", "Token", "token"]
        if entity_type == "place":
            priority_keys = ["Image", "image", "Portrait", "portrait", "TokenImage", "tokenImage", "Token", "token"]
        for key in priority_keys:
            value = record.get(key)
            if value:
                return value
        return ""

    def _resolve_scene_entity_portrait(self, entity):
        if not isinstance(entity, dict):
            return ""
        for key in ("portrait", "Portrait", "image", "Image", "tokenImage", "TokenImage", "token", "Token"):
            value = entity.get(key)
            if value:
                return value
        return ""

    def _iter_image_candidates(self, value):
        if value is None:
            return

        if isinstance(value, dict):
            for key in ("path", "Path", "file", "File", "image", "Image", "portrait", "Portrait", "value", "Value", "text", "Text"):
                if key in value:
                    yield from self._iter_image_candidates(value[key])
            return

        if isinstance(value, (list, tuple, set)):
            for item in value:
                yield from self._iter_image_candidates(item)
            return

        text = str(value).strip()
        if not text:
            return

        expanded = os.path.expandvars(os.path.expanduser(text))
        normalized = expanded.replace("\\", os.sep)
        yield normalized

        if not os.path.isabs(normalized):
            campaign_dir = ConfigHelper.get_campaign_dir()
            if campaign_dir:
                yield os.path.join(campaign_dir, normalized)
            if PORTRAIT_FOLDER:
                normalized_lower = normalized.replace("\\", "/").lower()
                if not normalized_lower.startswith("assets/"):
                    yield os.path.join(PORTRAIT_FOLDER, normalized)

    def _resolve_existing_image_path(self, portrait_path):
        seen = set()
        for candidate in self._iter_image_candidates(portrait_path):
            if not candidate:
                continue
            normalized = os.path.normpath(candidate)
            if normalized in seen:
                continue
            seen.add(normalized)
            if os.path.exists(normalized):
                return normalized
        return None

    def load_portrait(self, portrait_path, node_tag):
        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path:
            return None, (0, 0)
        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(MAX_PORTRAIT_SIZE, resample_method)
            portrait_image = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[node_tag] = portrait_image
            return portrait_image, img.size
        except Exception as e:
            print(f"Error loading portrait for {node_tag}: {e}")
            return None, (0, 0)

    def load_portrait_scaled(self, portrait_path, node_tag, scale=1.0):
        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path:
            return None, (0, 0)
        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            size = int(MAX_PORTRAIT_SIZE[0] * scale), int(MAX_PORTRAIT_SIZE[1] * scale)
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(size, resample_method)
            portrait_image = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[node_tag] = portrait_image
            return portrait_image, img.size
        except Exception as e:
            print(f"Error loading portrait for {node_tag}: {e}")
            return None, (0, 0)

    def load_thumbnail(self, portrait_path, cache_key, size):
        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path:
            return None
        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(size, resample_method)
            thumb = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[cache_key] = thumb
            return thumb
        except Exception as exc:
            print(f"Error loading portrait thumbnail '{portrait_path}': {exc}")
            return None

    def _entity_placeholder_color(self, entity_type):
        base = (entity_type or "").lower()
        color_map = {
            "npc": "#3f6fb5",
            "creature": "#b85a4a",
            "monster": "#b85a4a",
            "place": "#4f8750",
            "location": "#4f8750",
        }
        return color_map.get(base, "#666666")
    
    def draw_nodes(self):

        scale = self.canvas_scale

        GAP = int(5 * scale)
        PAD = int(10 * scale)

        # Prepare node_bboxes
        if not hasattr(self, "node_bboxes"):
            self.node_bboxes = {}
        else:
            self.node_bboxes.clear()

        # Helper to measure wrapped text height
        def measure_text_height(text, font_obj, wrap_width):
            temp_id = self.canvas.create_text(0, 0, text=text,
                                            font=font_obj,
                                            width=wrap_width,
                                            anchor="nw")
            bbox = self.canvas.bbox(temp_id)
            self.canvas.delete(temp_id)
            if bbox:
                return bbox[3] - bbox[1]
            return 0

        for node in self.graph["nodes"]:
            node_type = node["type"]
            node_name = node["name"]
            node_tag = f"{node_type}_{node_name.replace(' ', '_')}"
            x, y = node["x"], node["y"]
            data = node.get("data", {}) or {}
            title_text = node_name

            entity_entries = []

            if node_type == "scenario":
                summary = data.get("Summary", "")
                secret  = data.get("Secret", "")
                body_text = f"{summary}\nSecrets: {secret}" if secret else summary
            elif node_type == "scene":
                raw_text = data.get("Text") or data.get("text") or ""
                body_text = clean_longtext(raw_text, max_length=1200)
                body_text = body_text.strip()
                if len(body_text) > 700:
                    trimmed = body_text[:700]
                    cut = trimmed.rfind(" ")
                    if cut > 400:
                        trimmed = trimmed[:cut]
                    body_text = trimmed.rstrip() + "..."
                if not body_text:
                    body_text = "No scene notes provided."
                entities_raw = data.get("Entities") or data.get("entities") or []
                if isinstance(entities_raw, list):
                    entity_entries = [ent for ent in entities_raw if isinstance(ent, dict)]
                else:
                    entity_entries = []
            elif node_type == "place":
                desc   = data.get("Description", "")
                secret = data.get("Secret", "")
                body_text = f"{desc}\nSecret: {secret}" if secret else desc
            elif node_type == "creature":
                stats     = data.get("Stats", {})
                stats_text = stats.get("text", "No Stats") if isinstance(stats, dict) else str(stats)
                weakness  = data.get("Weakness", "")
                body_text = f"Stats: {stats_text}\nWeakness: {weakness}" if weakness else f"Stats: {stats_text}"
            else:
                traits = data.get("Traits", "")
                secret = data.get("Secret", "")
                body_text = f"{traits}\nSecret: {secret}" if secret else traits

            if node_type == "scene" and entity_entries:
                max_entities = 8
                if len(entity_entries) > max_entities:
                    entity_entries = entity_entries[:max_entities]
            else:
                entity_entries = entity_entries or []

            # Load portrait if applicable
            portrait = None
            p_w = p_h = 0
            if node_type in ["npc", "creature"]:
                portrait, (p_w, p_h) = self.load_portrait_scaled(
                    data.get("Portrait", ""),
                    node_tag,
                    scale
                )

            # Compute wrap width
            desired_chars_per_line = 45 if node_type == "scene" else 40
            avg_char_width = 7
            wrap_width = max(90, int(desired_chars_per_line * avg_char_width))
            if portrait and p_w > 0:
                wrap_width = max(wrap_width, 160)

            # Fonts
            title_font = tkFont.Font(family="Arial",
                                    size=max(1, int(10 * scale)),
                                    weight="bold")
            body_font = tkFont.Font(family="Arial",
                                    size=max(1, int(9 * scale)))

            thumb_size = max(24, int(40 * scale))
            thumb_gap = max(4, int(6 * scale))
            icons_height = thumb_size if entity_entries else 0
            icon_row_width = (
                len(entity_entries) * thumb_size
                + (len(entity_entries) - 1) * thumb_gap if entity_entries else 0
            )

            # Measure text heights
            title_h = measure_text_height(title_text, title_font, wrap_width)
            body_h  = measure_text_height(body_text,  body_font,  wrap_width)
            gap     = int(4 * scale)
            text_h  = title_h + gap + body_h

            # Node content size
            content_width  = max(p_w, wrap_width, icon_row_width)
            content_height = p_h + (GAP if portrait else 0) + text_h
            if entity_entries:
                content_height += GAP + icons_height
            min_w = content_width + 2 * PAD
            min_h = content_height + 2 * PAD

            # === BACKGROUND IMAGE: Post-it ===
            if self.postit_base:
                orig_w, orig_h = self.postit_base.size

                # scale so the post-it is at least as big as our minimum box
                scale_factor = max(min_w / orig_w, min_h / orig_h)
                node_width  = int(orig_w * scale_factor)
                node_height = int(orig_h * scale_factor)

                # resize with preserved aspect ratio
                scaled = self.postit_base.resize(
                    (node_width, node_height),
                    Image.Resampling.LANCZOS
                )

                # create PhotoImage and stash it
                photo = ImageTk.PhotoImage(scaled, master=self.canvas)
                self.node_holder_images[node_tag] = photo

                # draw the background post-it
                self.canvas.create_image(
                    x, y,
                    image=photo,
                    anchor="center",
                    tags=("node", node_tag)
                )

                # ── NEW: draw the semitransparent watermark icon ──
                icon = self.type_icons.get(node_type)
                if icon:
                    # compute top-left corner of the post-it
                    left = x - node_width  / 2
                    top  = y - node_height / 2
                    # margin inside the pad
                    margin = int(8 * scale)
                    icon_x = left + margin + icon.width()//2
                    icon_y = top  + margin + icon.height()//2
                    self.canvas.create_image(
                        icon_x, icon_y,
                        image=icon,
                        anchor="center",
                        tags=("node", node_tag)
                    )

            else:
                # fallback to plain rectangle
                node_width, node_height = min_w, min_h
                rect = self.canvas.create_rectangle(
                    x - node_width/2, y - node_height/2,
                    x + node_width/2, y + node_height/2,
                    fill=node.get("color","white"),
                    outline="black",
                    tags=("node", node_tag)
                )
                self.node_rectangles[node_tag] = rect

            # === PIN (unchanged) ===
            if hasattr(self, "pin_image") and self.pin_image:
                self.canvas.create_image(
                    x,
                    y - node_height // 2 - 10,
                    image=self.pin_image,
                    anchor="n",
                    tags=("node", node_tag)
                )

            # Compute content start coordinates
            left = x - node_width/2
            top  = y - node_height/2

            # 1) Portrait at top center
            if portrait and p_w > 0:
                portrait_x = x
                portrait_y = top + PAD + p_h/2 + 10
                self.canvas.create_image(
                    portrait_x, portrait_y,
                    image=portrait,
                    anchor="center",
                    tags=("node", node_tag)
                )
                text_top = portrait_y + p_h/2 + GAP
            else:
                text_top = top + PAD

            # 2) Title text
            title_id = self.canvas.create_text(
                x,
                text_top + title_h/2 + 10,
                text=title_text,
                font=title_font,
                fill="black",
                width=wrap_width,
                anchor="center",
                tags=("node", node_tag)
            )

            # 3) Body text
            body_id = self.canvas.create_text(
                x,
                text_top + title_h + gap + body_h/2 + 10,
                text=body_text,
                font=body_font,
                fill="black",
                width=wrap_width,
                anchor="center",
                tags=("node", node_tag)
            )

            if entity_entries:
                text_bottom = text_top + title_h + gap + body_h + 10
                row_width = icon_row_width
                row_left = x - row_width / 2
                icons_y = text_bottom + GAP + icons_height / 2
                for idx, entity in enumerate(entity_entries):
                    name = entity.get("name") or entity.get("Name") or ""
                    portrait_path = self._resolve_scene_entity_portrait(entity)
                    thumb_key = f"{node_tag}_thumb_{idx}"
                    icon = None
                    if portrait_path:
                        icon = self.load_thumbnail(portrait_path, thumb_key, (thumb_size, thumb_size))
                    if icon is None:
                        entity_type = (entity.get("type") or "").lower()
                        icon = self.type_icons.get(entity_type)
                    icon_x = row_left + idx * (thumb_size + thumb_gap) + thumb_size / 2
                    if icon is not None:
                        self.canvas.create_image(
                            icon_x,
                            icons_y,
                            image=icon,
                            anchor="center",
                            tags=("node", node_tag)
                        )
                    else:
                        color = self._entity_placeholder_color(entity.get("type"))
                        radius = thumb_size / 2
                        self.canvas.create_oval(
                            icon_x - radius,
                            icons_y - radius,
                            icon_x + radius,
                            icons_y + radius,
                            fill=color,
                            outline="",
                            tags=("node", node_tag)
                        )
                        initial = (name or "?")[0].upper()
                        marker_font = tkFont.Font(family="Arial", size=max(1, int(10 * scale)), weight="bold")
                        self.canvas.create_text(
                            icon_x,
                            icons_y,
                            text=initial,
                            font=marker_font,
                            fill="white",
                            tags=("node", node_tag)
                        )

            # Record bounding box for hit-testing
            self.node_bboxes[node_tag] = (
                x - node_width / 2,
                y - node_height/2,
                x + node_width / 2,
                y + node_height/2
            )

    def draw_links(self):
        self.canvas_link_items = {}
        for link in self.graph["links"]:
            self.draw_one_link(link)
        self.canvas.tag_lower("link_line")
        self.canvas.tag_raise("link_label")

    def draw_one_link(self, link):
        tag_from = link["from"]
        tag_to = link["to"]
        x1, y1 = self.node_positions.get(tag_from, (0, 0))
        x2, y2 = self.node_positions.get(tag_to, (0, 0))
        line_id = self.canvas.create_line(
            x1, y1, x2, y2, fill="black", width=2, tags=("link", "link_line")
        )
        self.canvas.tag_lower(line_id)
        self.canvas_link_items[line_id] = link

        text = (link.get("text") or "").strip()
        if text:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy) or 1
            offset = 18
            offset_x = -dy / length * offset
            offset_y = dx / length * offset
            label_x = mid_x + offset_x
            label_y = mid_y + offset_y
            label_font = tkFont.Font(family="Arial", size=max(8, int(9 * self.canvas_scale)))
            label_id = self.canvas.create_text(
                label_x,
                label_y,
                text=text,
                font=label_font,
                fill="#1f1f1f",
                width=180,
                justify="center",
                tags=("link", "link_label")
            )
            self.canvas_link_items[label_id] = link

    def start_drag(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        if "link" in tags:
            self.selected_node = None
            self.drag_start = None
            return
        node_tag = next((t for t in tags if t.startswith("scenario_")
                        or t.startswith("npc_")
                        or t.startswith("creature_")
                        or t.startswith("place_")
                        or t.startswith("scene_")), None)
        if node_tag:
            self.selected_node = node_tag
            self.selected_items = self.canvas.find_withtag(node_tag)
            self.drag_start = (x, y)
        else:
            self.selected_node = None
            self.drag_start = None

    def on_drag(self, event):
        if not self.selected_node or not self.drag_start:
            return

        # 1) canvas coords & delta
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        if dx == 0 and dy == 0:
            return

        # 2) move only the selected items
        for item_id in self.selected_items:
            self.canvas.move(item_id, dx, dy)

        # 3) update position in memory
        old_x, old_y = self.node_positions[self.selected_node]
        new_pos = (old_x + dx, old_y + dy)
        self.node_positions[self.selected_node] = new_pos
        for node in self.graph["nodes"]:
            tag = f"{node['type']}_{node['name'].replace(' ', '_')}"
            if tag == self.selected_node:
                node["x"], node["y"] = new_pos
                break

        # 4) redraw just the links
        self.canvas.delete("link")
        self.draw_links()                   # draws + tag_lower("link") :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}

        # 5) **re-stack** them above the background
        self.canvas.tag_lower("background")
        self.canvas.tag_raise("link", "background")
        # (optional) self.canvas.tag_raise("node")

        # 6) reset drag origin
        self.drag_start = (x, y)

    def on_double_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        if "link" in tags:
            self.edit_link_text(item_id)
            return
        node_tag = None
        for t in tags:
            if t.startswith("scenario_") or t.startswith("npc_") or t.startswith("creature_") or t.startswith("place_") or t.startswith("faction_"):
                node_tag = t
                break
        if not node_tag:
            return
        if node_tag.startswith("scenario_"):
            entity_type = "scenarios"
            entity_name = node_tag.replace("scenario_", "").replace("_", " ")
            entity = self.scenario
            wrapper=self.scenario_wrapper
        elif node_tag.startswith("npc_"):
            entity_type = "NPCs"
            entity_name = node_tag.replace("npc_", "").replace("_", " ")
            entity = self.npcs.get(entity_name)
            wrapper=self.npc_wrapper
        elif node_tag.startswith("creature_"):
            entity_type = "Creatures"
            entity_name = node_tag.replace("creature_", "").replace("_", " ")
            entity = self.creatures.get(entity_name)
            wrapper=self.creature_wrapper
            
        elif node_tag.startswith("place_"):
            entity_type = "Places"
            entity_name = node_tag.replace("place_", "").replace("_", " ")
            entity = self.places.get(entity_name)
            wrapper=self.place_wrapper
        elif node_tag.startswith("faction_"):
            entity_type = "Factions"
            entity_name = node_tag.replace("faction_", "").replace("_", " ")
            entity = self.factions.get(entity_name)
            wrapper=self.faction_wrapper
        else:
            return

        if not entity:
            messagebox.showerror("Error", f"{entity_type[:-1]} '{entity_name}' not found.")
            return

        template = load_template(entity_type.lower())
        GenericEditorWindow(None, entity, template,wrapper)

    def on_right_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        if "link" in tags:
            return
        node_tag = next((t for t in tags if t.startswith("scenario_")
                        or t.startswith("npc_")
                        or t.startswith("creature_")
                        or t.startswith("place_")), None)
        if node_tag:
            self.selected_node = node_tag
            self.show_node_menu(x, y)

    def _on_mousewheel_y(self, event):
        if self.canvas.yview() == (0.0, 1.0):  # No scrolling available
            return
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_mousewheel_x(self, event):
        if self.canvas.xview() == (0.0, 1.0):  # No scrolling available
            return
        if event.num == 4 or event.delta > 0:
            self.canvas.xview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.xview_scroll(1, "units")

    def show_node_menu(self, x, y):
        node_menu = Menu(self.canvas, tearoff=0)
        node_menu.add_command(label="Delete Node", command=self.delete_node)
        node_menu.add_separator()
        node_menu.add_command(label="Change Color", command=lambda: self.show_color_menu(x, y))
        if self.selected_node and (self.selected_node.startswith("npc_") or self.selected_node.startswith("creature_")):
            node_menu.add_command(label="Display Portrait", command=self.display_portrait_window)
        node_menu.post(int(x), int(y))

    def show_color_menu(self, x, y):
        COLORS = [
            "red", "green", "blue", "yellow", "purple",
            "orange", "pink", "cyan", "magenta", "lightgray"
        ]
        color_menu = Menu(self.canvas, tearoff=0)
        for color in COLORS:
            color_menu.add_command(label=color, command=lambda c=color: self.change_node_color(c))
        color_menu.post(int(x), int(y))

    def change_node_color(self, color):
        if not self.selected_node:
            return
        rect_id = self.node_rectangles.get(self.selected_node)
        if rect_id:
            self.canvas.itemconfig(rect_id, fill=color)
        for node in self.graph["nodes"]:
            if node["type"] == "scenario":
                tag = f"scenario_{node['name'].replace(' ', '_')}"
            elif node["type"] == "npc":
                tag = f"npc_{node['name'].replace(' ', '_')}"
            elif node["type"] == "creature":
                tag = f"creature_{node['name'].replace(' ', '_')}"
            else:
                tag = f"place_{node['name'].replace(' ', '_')}"
            if tag == self.selected_node:
                node["color"] = color
                break
        self.draw_graph()

    def delete_node(self):
        if not self.selected_node:
            return
        node_name = self.selected_node.split("_", 1)[-1].replace("_", " ")
        self.graph["nodes"] = [n for n in self.graph["nodes"] if n["name"] != node_name]
        self.graph["links"] = [l for l in self.graph["links"]
                            if l["from"] != self.selected_node and l["to"] != self.selected_node]
        if self.selected_node in self.node_positions:
            del self.node_positions[self.selected_node]
        self.draw_graph()

    def edit_link_text(self, item_id):
        link_record = self.canvas_link_items.get(item_id)
        if not link_record:
            return
        current_text = link_record.get("text", "")
        new_text = simpledialog.askstring(
            "Edit Link",
            "Link label:",
            initialvalue=current_text,
            parent=self,
        )
        if new_text is None:
            return
        new_text = new_text.strip()
        link_record["text"] = new_text
        link_data = link_record.get("link_data")
        if isinstance(link_data, dict):
            link_data["text"] = new_text
        self.canvas.delete("link")
        self.draw_links()
        try:
            self._persist_scene_links()
            self._save_scenario_changes()
        except Exception as exc:
            messagebox.showerror("Save Error", f"Failed to update link text: {exc}")

    def _get_scenario_scenes_list(self):
        scenes_raw = self.scenario.get("Scenes") if self.scenario else None
        if isinstance(scenes_raw, dict):
            if isinstance(scenes_raw.get("Scenes"), list):
                return scenes_raw["Scenes"]
            scenes_raw["Scenes"] = []
            return scenes_raw["Scenes"]
        if isinstance(scenes_raw, list):
            return scenes_raw
        if scenes_raw is None:
            self.scenario["Scenes"] = []
            return self.scenario["Scenes"]
        if isinstance(scenes_raw, str):
            self.scenario["Scenes"] = [scenes_raw]
        else:
            self.scenario["Scenes"] = [scenes_raw]
        return self.scenario["Scenes"]

    def _ensure_scene_entry(self, index):
        scenes_list = self._get_scenario_scenes_list()
        while len(scenes_list) <= index:
            scenes_list.append({})
        entry = scenes_list[index]
        if not isinstance(entry, dict):
            entry = {"Text": entry if isinstance(entry, str) else str(entry)}
            scenes_list[index] = entry
        return entry

    def _persist_scene_links(self):
        if not isinstance(self.scene_flow_scenes, list):
            return
        tag_lookup = self.scene_flow_scene_lookup or {}
        for scene in self.scene_flow_scenes:
            idx = scene.get("index")
            if idx is None:
                continue
            entry = self._ensure_scene_entry(idx)
            links_payload = []
            for link in scene.get("links", []):
                text_val = (link.get("text") or "").strip()
                link_record = {}
                target_scene = None
                target_tag = link.get("target_tag")
                if target_tag:
                    target_scene = tag_lookup.get(target_tag)
                target_idx = link.get("target_scene_index")
                if target_scene is None and isinstance(target_idx, int):
                    target_scene = next(
                        (sc for sc in self.scene_flow_scenes if sc.get("index") == target_idx),
                        None,
                    )
                if target_scene:
                    target_title = target_scene.get("title") or target_scene.get("display_name")
                    if target_title:
                        link_record["Target"] = target_title
                    else:
                        link_record["Target"] = target_scene.get("index", 0) + 1
                    link_record["TargetIndex"] = target_scene.get("index")
                else:
                    raw_target = link.get("target") or link.get("target_key") or link.get("target_index")
                    if isinstance(raw_target, (int, float)):
                        link_record["Target"] = int(raw_target)
                    elif raw_target:
                        link_record["Target"] = raw_target
                if text_val:
                    link_record["Text"] = text_val
                links_payload.append(link_record)
            entry["Links"] = links_payload

    def _save_scenario_changes(self):
        if not self.scenario_wrapper or not self.scenario:
            return
        try:
            items = self.scenario_wrapper.load_items()
            title = self.scenario.get("Title")
            saved = False
            for idx, item in enumerate(items):
                if item.get("Title") == title:
                    items[idx] = self.scenario
                    saved = True
                    break
            if not saved:
                items.append(self.scenario)
            self.scenario_wrapper.save_items(items)
        except Exception as exc:
            raise RuntimeError(exc)

    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json")
        if file_path:
            for node in self.graph["nodes"]:
                if node["type"] == "scenario":
                    node_tag = f"scenario_{node['name'].replace(' ', '_')}"
                elif node["type"] == "npc":
                    node_tag = f"npc_{node['name'].replace(' ', '_')}"
                elif node["type"] == "creature":
                    node_tag = f"creature_{node['name'].replace(' ', '_')}"
                elif node["type"] == "place":
                    node_tag = f"place_{node['name'].replace(' ', '_')}"
                elif node["type"] == "scene":
                    node_tag = f"scene_{node['name'].replace(' ', '_')}"
                else:
                    node_tag = f"{node['type']}_{node['name'].replace(' ', '_')}"
                x, y = self.node_positions.get(node_tag, (node["x"], node["y"]))
                node["x"], node["y"] = x, y
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.graph, f, indent=2)

    def load_graph(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                self.graph = json.load(f)
            self.node_positions.clear()
            for node in self.graph["nodes"]:
                if node["type"] == "scenario":
                    node_tag = f"scenario_{node['name'].replace(' ', '_')}"
                elif node["type"] == "npc":
                    node_tag = f"npc_{node['name'].replace(' ', '_')}"
                elif node["type"] == "creature":
                    node_tag = f"creature_{node['name'].replace(' ', '_')}"
                elif node["type"] == "place":
                    node_tag = f"place_{node['name'].replace(' ', '_')}"
                elif node["type"] == "scene":
                    node_tag = f"scene_{node['name'].replace(' ', '_')}"
                else:
                    node_tag = f"{node['type']}_{node['name'].replace(' ', '_')}"
                self.node_positions[node_tag] = (node["x"], node["y"])
            self.draw_graph()
        # Try to find the scenario node and set self.scenario
        scenario_node = next((n for n in self.graph["nodes"] if n["type"] == "scenario"), None)
        if scenario_node:
            title = scenario_node["name"]
            all_scenarios = self.scenario_wrapper.load_items()
            matched = next((s for s in all_scenarios if s.get("Title") == title), None)
            if matched:
                self.scenario = matched
            else:
                print(f"[WARNING] Scenario titled '{title}' not found in data.")
        for node in self.graph["nodes"]:
            tag = f"{node['type']}_{node['name'].replace(' ', '_')}"
            self.original_positions[tag] = (node["x"], node["y"])
        
        # --- Scroll to center on the scenario node ---
        self.canvas.update_idletasks()
        scenario_node = next((n for n in self.graph["nodes"] if n["type"] == "scenario"), None)
        if scenario_node:
            tag = f"scenario_{scenario_node['name'].replace(' ', '_')}"
            if tag in self.node_positions:
                x, y = self.node_positions[tag]

                # Get canvas scroll region and view dimensions
                scroll_x0, scroll_y0, scroll_x1, scroll_y1 = self.canvas.bbox("all")
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                # Compute scroll fractions
                scroll_x_frac = max(0.0, min(1.0, (x - canvas_width / 2 - scroll_x0) / (scroll_x1 - scroll_x0)))
                scroll_y_frac = max(0.0, min(1.0, (y - canvas_height / 2 - scroll_y0) / (scroll_y1 - scroll_y0)))

                self.canvas.xview_moveto(scroll_x_frac)
                self.canvas.yview_moveto(scroll_y_frac)
        
        
    def get_state(self):
        return {
            "graph": self.graph,
            "node_positions": self.node_positions,
        }

    def set_state(self, state):
        self.graph = state.get("graph", {})
        self.node_positions = state.get("node_positions", {})
        self.draw_graph()
    def load_icon(self,path, size, opacity):
        img = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        alpha = img.split()[3].point(lambda p: int(p * opacity))
        img.putalpha(alpha)
        return ImageTk.PhotoImage(img, master=self._canvas)
        
def make_watermarked_postit(base_path, icon_path, size=(200,200), icon_size=32, margin=8, opacity=80):
        # 1) load base
        base = Image.open(base_path).convert("RGBA")
        base = base.resize(size, Image.ANTIALIAS)

        # 2) load & prep icon
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((icon_size, icon_size), Image.ANTIALIAS)
        # tint down alpha
        alpha = icon.split()[3].point(lambda p: p * (opacity/100))
        icon.putalpha(alpha)

        # 3) compute paste coords (bottom-right corner)
        bx, by = base.size
        ix, iy = icon.size
        pos = (bx - ix - margin, by - iy - margin)

        # 4) composite and convert to PhotoImage
        base.paste(icon, pos, icon)
        return ImageTk.PhotoImage(base)

    
