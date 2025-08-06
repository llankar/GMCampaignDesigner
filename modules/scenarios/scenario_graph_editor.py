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
from tkinter import filedialog, messagebox, ttk, Menu
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
            "creature": self.load_icon("assets/creature_icon.png", 32, 0.6)
        }
        
        # Graph structure.
        self.graph = {"nodes": [], "links": []}
        self.node_positions = {}   # Maps node_tag -> (x, y)
        self.node_rectangles = {}  # Maps node_tag -> rectangle_id
        self.selected_node = None
        self.selected_items = []
        self.drag_start = None
        self.original_positions = {}

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
        ctk.CTkButton(toolbar, text="Save Graph", command=self.save_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Load Graph", command=self.load_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Reset Zoom", command=self.reset_zoom).pack(side="left", padx=5)

    
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

    def load_portrait(self, portrait_path, node_tag):
        if not portrait_path or not os.path.exists(portrait_path):
            return None, (0, 0)
        try:
            img = Image.open(portrait_path)
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(MAX_PORTRAIT_SIZE, resample_method)
            portrait_image = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[node_tag] = portrait_image
            return portrait_image, img.size
        except Exception as e:
            print(f"Error loading portrait for {node_tag}: {e}")
            return None, (0, 0)

    def load_portrait_scaled(self, portrait_path, node_tag, scale=1.0):
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
            data = node.get("data", {})
            title_text = node_name

            # Determine body text
            if node_type == "scenario":
                summary = data.get("Summary", "")
                secret  = data.get("Secret", "")
                body_text = f"{summary}\nSecrets: {secret}" if secret else summary
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
            desired_chars_per_line = 40
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

            # Measure text heights
            title_h = measure_text_height(title_text, title_font, wrap_width)
            body_h  = measure_text_height(body_text,  body_font,  wrap_width)
            gap     = int(4 * scale)
            text_h  = title_h + gap + body_h

            # Node content size
            content_width  = max(p_w, wrap_width)
            content_height = p_h + (GAP if portrait else 0) + text_h
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
            self.canvas.create_text(
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
            self.canvas.create_text(
                x,
                text_top + title_h + gap + body_h/2 + 10,
                text=body_text,
                font=body_font,
                fill="black",
                width=wrap_width,
                anchor="center",
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
        for link in self.graph["links"]:
            self.draw_one_link(link)
        self.canvas.tag_lower("link")

    def draw_one_link(self, link):
        tag_from = link["from"]
        tag_to = link["to"]
        x1, y1 = self.node_positions.get(tag_from, (0, 0))
        x2, y2 = self.node_positions.get(tag_to, (0, 0))
        line_id = self.canvas.create_line(
            x1, y1, x2, y2, fill="black", width=2, tags=("link",)
        )
        self.canvas.tag_lower(line_id)

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
                        or t.startswith("place_")), None)
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
                else:
                    node_tag = f"place_{node['name'].replace(' ', '_')}"
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
                else:
                    node_tag = f"place_{node['name'].replace(' ', '_')}"
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

    