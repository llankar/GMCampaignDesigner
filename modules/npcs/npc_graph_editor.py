import json
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk, Menu
from PIL import Image, ImageTk
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.template_loader import load_template
from modules.generic.generic_model_wrapper import GenericModelWrapper
import math
from PIL import Image, ImageTk
#import logging

from modules.npcs import npc_opener
import tkinter as tk  # standard tkinter
from PIL import Image, ImageTk
import os
import textwrap
from modules.ui.image_viewer import show_portrait
from modules.helpers.config_helper import ConfigHelper

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

#logging.basicConfig(level=logging.ERROR)

# Constants for portrait folder and max portrait size
PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)

# ─────────────────────────────────────────────────────────────────────────
# CLASS: NPCGraphEditor
# A custom graph editor for NPCs and factions using CustomTkinter.
# Supports adding nodes, links, dragging, context menus, and saving/loading.
# ─────────────────────────────────────────────────────────────────────────
class NPCGraphEditor(ctk.CTkFrame):
    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: __init__
    # Initializes the editor, loads NPC data, sets up graph structures, canvas, 
    # scrollbars, and event bindings.
    # ─────────────────────────────────────────────────────────────────────────
    def __init__(self, master, npc_wrapper: GenericModelWrapper, faction_wrapper: GenericModelWrapper, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.selected_shape = None
        self.link_canvas_ids = {}
        self.npc_wrapper = npc_wrapper
        self.faction_wrapper = faction_wrapper
        self.npcs = {npc["Name"]: npc for npc in self.npc_wrapper.load_items()}
        self.canvas_scale = 1.0
        self.zoom_factor = 1.1
        # Graph structure to hold nodes and links
        self.graph = {
            "nodes": [],
            "links": [],
            "shapes": []  # 
        }
        self.original_positions = {}  # Backup for original NPC positions
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
        # Variables for selection and dragging
        self.selected_node = None
        self.selected_items = []  # All canvas items belonging to the selected node
        self.drag_start = None    # Starting point for dragging
        self.selected_link = None # Currently selected link for context menus
        
        # Initialize the toolbar and canvas frame
        self.init_toolbar()
        self.canvas_frame = ctk.CTkFrame(self)
        self.canvas_frame.pack(fill="both", expand=True)
        self.canvas = ctk.CTkCanvas(self.canvas_frame, bg="#2B2B2B", highlightthickness=0)
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
        bg_path     = os.path.join("assets", "images", "corkboard_bg.png")

        if os.path.exists(postit_path):
            self.postit_base = Image.open(postit_path).convert("RGBA")
        else:
            self.postit_base = None

        if os.path.exists(pin_path):
            pin_img = Image.open(pin_path)
            size = int(32 * self.canvas_scale)
            pin_img = pin_img.resize((size, size), Image.Resampling.LANCZOS)
            self.pin_image = ImageTk.PhotoImage(pin_img, master=self.canvas)
        else:
            self.pin_image = None

        # draw corkboard background once the canvas exists
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
    # Bind double-click on any NPC element to open the editor window
        self.canvas.bind("<Double-Button-1>", self.open_npc_editor)

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
                node_tag = f"npc_{node['npc_name'].replace(' ', '_')}"
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
 # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: open_npc_editor
    # Opens the Generic Editor Window for the clicked NPC.
    # ─────────────────────────────────────────────────────────────────────────
    def open_npc_editor(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        npc_tag = next((t for t in tags if t.startswith("npc_")), None)
        if not npc_tag:
            return
        # Convert tag back to NPC name (assuming spaces were replaced with underscores)
        npc_name = npc_tag.replace("npc_", "").replace("_", " ")
        npc_item = self.npcs.get(npc_name)
        if not npc_item:
            messagebox.showerror("Error", f"NPC '{npc_name}' not found in data.")
            return
        print(f"Opening editor for NPC: {npc_name}")
        npc_opener.open_npc_editor_window(npc_name)
        # ─────────────────────────────────────────────────────────────────────────
    def display_portrait_window(self):
        """Display the NPC's portrait in a normal window (with decorations) that is
        sized and positioned to cover the second monitor (if available).  
        """
        #logging.debug("Entering display_portrait_window")
        
        # Check if a valid NPC is selected.
        if not self.selected_node or not self.selected_node.startswith("npc_"):
            messagebox.showerror("Error", "No NPC selected.")
           #logging.error("No NPC selected.")
            return

        # Extract NPC name from the node tag.
        npc_name = self.selected_node.replace("npc_", "").replace("_", " ")
       #logging.debug(f"Extracted NPC name: {npc_name}")

        npc_data = self.npcs.get(npc_name)
        if not npc_data:
            messagebox.showerror("Error", f"NPC '{npc_name}' not found.")
           #logging.error(f"NPC '{npc_name}' not found.")
            return

        portrait_path = npc_data.get("Portrait", "")
       #logging.debug(f"Portrait path: {portrait_path}")
        if portrait_path and not os.path.isabs(portrait_path):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
            if os.path.exists(candidate):
                portrait_path = candidate
        if not portrait_path or not os.path.exists(portrait_path):
            messagebox.showerror("Error", "No valid portrait found for this NPC.")
           #logging.error("No valid portrait found.")
            return
        show_portrait(portrait_path, npc_name)

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
        self.node_positions = state.get("node_positions", {}).copy()
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

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: init_toolbar
    # Creates a toolbar with buttons for adding NPCs, factions, saving, loading, and adding links.
    # ─────────────────────────────────────────────────────────────────────────
    def init_toolbar(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(toolbar, text="Add NPC", command=self.add_npc).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Add Faction", command=self.add_faction).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Add Link", command=self.start_link_creation).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Save", command=self.save_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Load", command=self.load_graph).pack(side="left", padx=5)

        # 🆕 Add Shape Buttons
        ctk.CTkButton(toolbar, text="Add Rectangle", command=lambda: self.add_shape("rectangle")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Add Oval", command=lambda: self.add_shape("oval")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Reset Zoom", command=self.reset_zoom).pack(side="left", padx=5)

    def reset_zoom(self):
        self.canvas_scale = 1.0

        # Restore NPC node positions
        for node in self.graph["nodes"]:
            tag = f"npc_{node['npc_name'].replace(' ', '_')}"
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
        self.first_node = next((t for t in tags if t.startswith("npc_")), None)
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
        self.second_node = next((t for t in tags if t.startswith("npc_")), None)
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
            messagebox.showerror("Error", "One or both NPCs not found.")
            return
        npc_name1 = tag1.replace("npc_", "").replace("_", " ")
        npc_name2 = tag2.replace("npc_", "").replace("_", " ")
        self.graph["links"].append({
            "npc_name1": npc_name1,
            "npc_name2": npc_name2,
            "text": link_text,
            "arrow_mode": "both"  # Options: "none", "start", "end", "both"
        })
        self.draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_npc
    # Opens an NPC selection dialog and binds the next click to place the NPC.
    # ─────────────────────────────────────────────────────────────────────────
    def add_npc(self):
        def on_npc_selected(npc_name):
            # Lookup the full NPC dictionary using the npc wrapper.
            npc_list = self.npc_wrapper.load_items()
            selected_npc = None
            for npc in npc_list:
                if npc.get("Name") == npc_name:
                    selected_npc = npc
                    break
            if not selected_npc:
                messagebox.showerror("Error", f"NPC '{npc_name}' not found.")
                return
            self.pending_npc = selected_npc
            if dialog.winfo_exists():
                dialog.destroy()
            self.canvas.bind("<Button-1>", self.place_pending_npc)

        npc_template = load_template("npcs")
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select NPC")
        dialog.geometry("1200x800")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        # The new GenericListSelectionView returns the NPC name (string)
        selection_view = GenericListSelectionView(
            dialog,
            "NPCs",
            self.npc_wrapper,
            npc_template,
            on_select_callback=lambda et, npc: on_npc_selected(npc)
        )
        selection_view.pack(fill="both", expand=True)
        dialog.wait_window()




    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: place_pending_npc
    # Places the selected NPC at the mouse click location and updates the graph.
    # ─────────────────────────────────────────────────────────────────────────
    def place_pending_npc(self, event):
        npc_name = self.pending_npc["Name"]
       
        x0 = self.canvas.canvasx(event.x)
        y0 = self.canvas.canvasy(event.y)
        # new: derive a unique tag
        base = f"npc_{npc_name.replace(' ', '_')}"
        tag = base
        i = 1
        # bump the suffix until it’s unused
        while tag in self.node_positions:
            tag = f"{base}_{i}"
            i += 1

        self.graph["nodes"].append({
            "npc_name": npc_name,
            "tag":       tag,      # store it on the node
            "x":         x0,
            "y":         y0,
            # … any other fields …
        })
        self.node_positions[tag] = (x0, y0)
      
        self.pending_npc = None
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.start_drag)
        self.draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_faction
    # Opens a faction selection dialog and adds all NPCs from the selected faction.
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

            # find all NPCs that list this faction
            faction_npcs = []
            for npc in self.npcs.values():
                fv = npc.get("Factions")
                if isinstance(fv, list) and faction_name in fv:
                    faction_npcs.append(npc)
                elif fv == faction_name:
                    faction_npcs.append(npc)

            if not faction_npcs:
                messagebox.showinfo("No NPCs", f"No NPCs found in faction '{faction_name}'.")
                return

            # ── 3) Place each NPC as its own post-it ─────────────────────
            start_x, start_y = 100, 100
            spacing = int(120 * self.canvas_scale)
            for i, npc in enumerate(faction_npcs):
                name = npc["Name"]
                # generate a unique tag
                base = f"npc_{name.replace(' ', '_')}"
                tag = base
                suffix = 1
                while tag in self.node_positions:
                    tag = f"{base}_{suffix}"
                    suffix += 1

                x = start_x + i * spacing
                y = start_y

                # record in the underlying graph
                self.graph["nodes"].append({
                    "npc_name": name,
                    "tag":       tag,
                    "x":         x,
                    "y":         y,
                    "color":    "#1D3572"
                })
                # record its canvas position
                self.node_positions[tag] = (x, y)

            # ── 4) Restore drag handlers so these new nodes can be moved ───
            self.canvas.unbind("<Button-1>")
            self.canvas.bind("<Button-1>",        self.start_drag)
            self.canvas.bind("<B1-Motion>",       self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.end_drag)

            # ── 5) Redraw everything (post-its, portraits, links, etc.) ────
            self.draw_graph()

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
        node_name = node_tag.replace("npc_", "").replace("_", " ")
        for link in self.graph["links"]:
            if node_name in (link["npc_name1"], link["npc_name2"]):
                key = (link["npc_name1"], link["npc_name2"])
                canvas_ids = self.link_canvas_ids.get(key)
                if canvas_ids:
                    tag1 = f"npc_{link['npc_name1'].replace(' ', '_')}"
                    tag2 = f"npc_{link['npc_name2'].replace(' ', '_')}"
                    x1, y1 = self.node_positions.get(tag1, (0, 0))
                    x2, y2 = self.node_positions.get(tag2, (0, 0))

                    # Update line coordinates directly
                    self.canvas.coords(canvas_ids["line"], x1, y1, x2, y2)

                    # Update text position
                    mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                    self.canvas.coords(canvas_ids["text"], mid_x, mid_y)

                    # Delete old arrowheads
                    for arrow_id in canvas_ids["arrows"]:
                        self.canvas.delete(arrow_id)
                    canvas_ids["arrows"] = []

                    # Redraw arrowheads at new position
                    arrow_mode = link.get("arrow_mode", "end")
                    if arrow_mode in ("start", "both"):
                        arrow_id = self.draw_arrowhead(x1, y1, x2, y2, tag1)
                        canvas_ids["arrows"].append(arrow_id)
                    if arrow_mode in ("end", "both"):
                        arrow_id = self.draw_arrowhead(x2, y2, x1, y1, tag2)
                        canvas_ids["arrows"].append(arrow_id)

    
    def update_links_for_node(self, node_tag):
        # Delete only existing links and associated arrowheads/text
        self.canvas.delete("link")
        self.canvas.delete("arrowhead")
        self.canvas.delete("link_text")

        # Redraw only links involving the moved node
        node_name = node_tag.replace("npc_", "").replace("_", " ")
        affected_links = [
            link for link in self.graph["links"]
            if link["npc_name1"] == node_name or link["npc_name2"] == node_name
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
        if "link" in tags:
            self.show_link_menu(int(x), int(y))
            self.selected_link = self.get_link_by_position(x, y)
        elif any(tag.startswith("npc_") for tag in tags):
            self.selected_node = next((t for t in tags if t.startswith("npc_")), None)
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
        node_menu.post(int(x), int(y))

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: set_arrow_mode
    # Sets the arrow_mode for the currently selected link.
    # ─────────────────────────────────────────────────────────────────────────
    def set_arrow_mode(self, new_mode):
        if not self.selected_link:
            return
        for link in self.graph["links"]:
            if (link["npc_name1"] == self.selected_link["npc_name1"]
                    and link["npc_name2"] == self.selected_link["npc_name2"]):
                link["arrow_mode"] = new_mode
                break
        self.draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: delete_node
    # Deletes the currently selected node and removes any links involving it.
    # ─────────────────────────────────────────────────────────────────────────
    def delete_node(self):
        if not self.selected_node:
            return

        tag = self.selected_node
        # 1) Remove all canvas items for this node (post-it, pin, portrait, text)
        self.canvas.delete(tag)

        # 2) Compute the NPC’s name and remove from the model
        node_name = tag.replace("npc_", "").replace("_", " ")
        self.graph["nodes"] = [
            n for n in self.graph["nodes"]
            if n["npc_name"] != node_name
        ]
        self.graph["links"] = [
            l for l in self.graph["links"]
            if l["npc_name1"] != node_name and l["npc_name2"] != node_name
        ]

        # 3) Drop its saved position
        self.node_positions.pop(tag, None)

        # 4) Redraw the rest of the graph
        self.draw_graph()

    def redraw_after_drag(self):
        self.draw_graph()
        self._redraw_scheduled = False


    
        # — ADDED: draw the corkboard background once canvas exists
    def _on_canvas_configure(self, event):
        """
        Whenever the canvas is resized (or we manually call this),
        redraw the background to fill the full width/height.
        """
        bg_path = os.path.join("assets", "images", "corkboard_bg.png")
        if os.path.exists(bg_path):
            # Load & resize the corkboard to exactly event.width×event.height
            img = Image.open(bg_path)
            img = img.resize((event.width, event.height), Image.Resampling.LANCZOS)
            self.background_photo = ImageTk.PhotoImage(img, master=self.canvas)

            # Remove any old background image
            self.canvas.delete("background")

            # Draw the new one, always tagged "background"
            self.background_id = self.canvas.create_image(
                0, 0,
                image=self.background_photo,
                anchor="nw",
                tags="background"
            )
            self.canvas.tag_lower("background")
    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_nodes
    # Iterates over all nodes in the graph, draws their rectangles, portraits, and labels,
    # and calculates/stores their bounding boxes.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_nodes(self):
        scale = self.canvas_scale
        GAP = int(5 * scale)
        PAD = int(10 * scale)

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

        for node in self.graph["nodes"]:
            npc_name = node["npc_name"]
            tag = node.get("tag")
            x, y = self.node_positions.get(tag, (node["x"], node["y"]))

            # ── Load NPC data ─────────────────────────────────────────
            data = self.npcs.get(npc_name, {})
            role = data.get("Role", "")
            fv = data.get("Factions", "")
            fv_text = ", ".join(fv) if isinstance(fv, list) else str(fv) if fv else ""

            # ── Load & scale portrait ─────────────────────────────────
            portrait_img = None
            p_w = p_h = 0
            portrait_path = data.get("Portrait", "")
            if portrait_path and not os.path.isabs(portrait_path):
                candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
                if os.path.exists(candidate):
                    portrait_path = candidate
            if portrait_path and os.path.exists(portrait_path):
                img = Image.open(portrait_path)
                ow, oh = img.size
                max_w = int(80 * scale)
                max_h = int(80 * scale)
                ratio = min(max_w/ow, max_h/oh, 1.0)
                p_w, p_h = int(ow*ratio), int(oh*ratio)
                img = img.resize((p_w, p_h), Image.Resampling.LANCZOS)
                portrait_img = ImageTk.PhotoImage(img, master=self.canvas)
                self.node_images[tag] = portrait_img

            # ── Prepare title & body text ────────────────────────────
            title_text = npc_name
            body_text = "\n".join(filter(None, [role, fv_text]))

            # ── Font definitions ─────────────────────────────────────
            title_font = ("Arial", max(1, int(10 * scale)), "bold")
            body_font  = ("Arial", max(1, int(9  * scale)))

            # ── Compute wrap width & measure text heights ────────────
            wrap_width = max(p_w, int(150 * scale)) - 2 * PAD
            title_h = measure_text_height(title_text, title_font, wrap_width)
            body_h  = measure_text_height(body_text,  body_font,  wrap_width) if body_text else 0

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

            # ── 1) Draw the post-it background ───────────────────────
            if self.postit_base:
                ow, oh = self.postit_base.size
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
            if self.pin_image:
                self.canvas.create_image(
                    x,
                    y - node_h // 2 - int(8 * scale)-5,
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
                    fill="black",
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
                    fill="black",
                    width=wrap_width,
                    anchor="n",
                    justify="center",
                    tags=(tag, "node_fg", "node")
                )

            # ── 6) Store bounding box for links ──────────────────────
            self.node_bboxes[tag] = (
                x - node_w / 2, y - node_h / 2,
                x + node_w / 2, y + node_h / 2
            )

            # ── 7) Layer foreground above background ────────────────
            self.canvas.tag_raise("node_fg", "node_bg")

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_all_links
    # Iterates over all links in the graph and draws them, then lowers link elements behind nodes.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_all_links(self):
        for link in self.graph["links"]:
            self.draw_one_link(link)
        self.canvas.tag_lower("link")

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_one_link
    # Draws a single link between two nodes, including its arrowheads (if any) and text.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_one_link(self, link):
        tag1 = f"npc_{link['npc_name1'].replace(' ', '_')}"
        tag2 = f"npc_{link['npc_name2'].replace(' ', '_')}"
        x1, y1 = self.node_positions.get(tag1, (0, 0))
        x2, y2 = self.node_positions.get(tag2, (0, 0))

        line_id = self.canvas.create_line(x1, y1, x2, y2, fill="#5BB8FF", tags=("link",))
        arrow_mode = link.get("arrow_mode", "end")

        arrow_ids = []
        if arrow_mode in ("start", "both"):
            arrow_ids.append(self.draw_arrowhead(x1, y1, x2, y2, tag1))
        if arrow_mode in ("end", "both"):
            arrow_ids.append(self.draw_arrowhead(x2, y2, x1, y1, tag2))

        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        scale = self.canvas_scale
        font_size = max(1, int(10 * scale))

        text_id = self.canvas.create_text(
            mid_x, mid_y,
            text=link["text"],
            fill="white",
            font=("Arial", font_size, "bold"),
            tags=("link_text",)
        )

        # Store Canvas IDs clearly linked by npc pair
        key = (link["npc_name1"], link["npc_name2"])
        self.link_canvas_ids[key] = {
            "line": line_id,
            "arrows": arrow_ids,
            "text": text_id
        }


    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_arrowhead
    # Draws a triangular arrowhead near a node, offset outside the node's bounding box.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_arrowhead(self, start_x, start_y, end_x, end_y, node_tag):
        arrow_length = 10
        angle = math.atan2(end_y - start_y, end_x - start_x)
        left, top, right, bottom = self.node_bboxes.get(
            node_tag, (start_x - 50, start_y - 25, start_x + 50, start_y + 25)
        )
        half_w = (right - left) / 2
        half_h = (bottom - top) / 2
        node_radius = math.sqrt(half_w**2 + half_h**2)
        arrow_offset_extra = -20
        arrow_offset = node_radius + arrow_offset_extra
        arrow_apex_x = start_x + arrow_offset * math.cos(angle)
        arrow_apex_y = start_y + arrow_offset * math.sin(angle)

        # RETURN the polygon ID so it can be deleted later
        return self.canvas.create_polygon(
            arrow_apex_x, arrow_apex_y,
            arrow_apex_x + arrow_length * math.cos(angle + math.pi / 6),
            arrow_apex_y + arrow_length * math.sin(angle + math.pi / 6),
            arrow_apex_x + arrow_length * math.cos(angle - math.pi / 6),
            arrow_apex_y + arrow_length * math.sin(angle - math.pi / 6),
            fill="#5BB8FF",
            outline="white",
            tags=("link", "arrowhead")
    )


    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: save_graph
    # Updates node positions and saves the current graph (nodes and links) to a JSON file.
    # ─────────────────────────────────────────────────────────────────────────
    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json")
        if file_path:
            for node in self.graph["nodes"]:
                tag = f"npc_{node['npc_name'].replace(' ', '_')}"
                x, y = self.node_positions.get(tag, (node["x"], node["y"]))
                node["x"] = x
                node["y"] = y
            for link in self.graph["links"]:
                if "arrow_mode" not in link:
                    link["arrow_mode"] = "both"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.graph, f, indent=2)

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
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if not path:
                return
        with open(path, 'r', encoding='utf-8') as f:
            self.graph = json.load(f)
        self.graph.setdefault("shapes", [])

        # ── 2) Ensure every node dict has its own unique `tag` ────────────────────
        seen = set()
        for node in self.graph["nodes"]:
            base = f"npc_{node['npc_name'].replace(' ', '_')}"
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
        for link in self.graph["links"]:
            link.setdefault("arrow_mode", "both")

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
                if node["npc_name"] == self.selected_node.replace("npc_", "").replace("_", " "):
                    node["color"] = color
                    break
    def change_shape_color(self, tag, color):
        self.canvas.itemconfig(tag, fill=color)
        shape = self.shapes.get(tag)
        if shape:
            shape["color"] = color

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

    def send_to_back(self, tag=None):
        tag = tag or self.selected_shape
        if not tag:
            return
        self.canvas.tag_raise(tag, "background")
        self.canvas.tag_lower(tag, "link")

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
            npc_name1 = link["npc_name1"]
            npc_name2 = link["npc_name2"]
            tag1 = f"npc_{npc_name1.replace(' ', '_')}"
            tag2 = f"npc_{npc_name2.replace(' ', '_')}"
            x1, y1 = self.node_positions.get(tag1, (0, 0))
            x2, y2 = self.node_positions.get(tag2, (0, 0))
            distance = self.distance_point_to_line(x, y, x1, y1, x2, y2)
            if distance < threshold:
                return link
        return None


    def add_shape(self, shape_type):
        x, y = 200, 200
        width, height = 120, 80
        tag = f"shape_{self.shape_counter}"
        self.shape_counter += 1
        shape = {"type": shape_type, "x": x, "y": y, "w": width, "h": height, "color": "lightgray", "tag": tag}
        self.graph["shapes"].append(shape)
        self.shapes[tag] = shape
        self.draw_shape(shape)

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
        # Sort shapes based on the stored z-index.
        shapes_sorted = sorted(self.graph.get("shapes", []), key=lambda s: s.get("z", 0))
        for shape in shapes_sorted:
            self.shapes[shape["tag"]] = shape
            self.draw_shape(shape)

    def save_graph(self, path=None):
        # 1) Prompt for filename if needed
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON Files", "*.json")],
            )
            if not path:
                return

        # 2) Update each node entry with its unique tag and current x,y
        for node in self.graph["nodes"]:
            tag = node.get("tag")
            # fallback to name‐based tag if somehow missing
            if not tag:
                tag = f"npc_{node['npc_name'].replace(' ', '_')}"
                node["tag"] = tag

            # Pull the live position from self.node_positions
            pos = self.node_positions.get(tag)
            if pos:
                node["x"], node["y"] = pos
            else:
                # if for some reason it's missing, leave whatever was there
                pass

        # 3) Write out the full graph dict
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.graph, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")
            return
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
    def draw_graph(self):
        #self.canvas.delete("shape")
        #self.canvas.delete("link")
        #self.canvas.delete("link_text")
        # ── 1) Remove everything except the corkboard background ──
        #    we keep only items tagged “background”
        for item in self.canvas.find_all():
            if "background" not in self.canvas.gettags(item):
                self.canvas.delete(item)
        self.node_bboxes = {}
        self.draw_all_shapes()
        self.draw_nodes()
        self.draw_all_links()
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
        if self.canvas.find_withtag("link"):
            self.canvas.tag_raise("link", "background")
        # then make sure nodes (post-its) are on top of everything
        if self.canvas.find_withtag("node"):
            self.canvas.tag_raise("node")
        # finally keep shapes just above background but below links/nodes
        if self.canvas.find_withtag("shape"):
            self.canvas.tag_raise("shape", "background")


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
            # First check for an NPC node tag
            for tag in tags:
                if tag.startswith("npc_"):
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
        self.selected_node = None
        self.selected_shape = None
        self.selected_items = []
        self.drag_start = None
