import json
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk, Menu
from PIL import Image, ImageTk
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.template_loader import load_template
from modules.generic.generic_model_wrapper import GenericModelWrapper
import math
#import logging
from screeninfo import get_monitors
from modules.pcs import pc_opener
import tkinter as tk  # standard tkinter
from PIL import Image, ImageTk
import os, ctypes
from ctypes import wintypes
import textwrap
import re
from tkinter.font import Font  # add at top of file
from modules.ui.image_viewer import show_portrait
from modules.helpers.config_helper import ConfigHelper

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Helper function to get monitor information using ctypes and Windows API.
def get_monitors():
    monitors = []
    def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        monitors.append((rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top))
        return True
    MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL,
                                          wintypes.HMONITOR,
                                          wintypes.HDC,
                                          ctypes.POINTER(wintypes.RECT),
                                          wintypes.LPARAM)
    ctypes.windll.user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(monitor_enum_proc), 0)
    return monitors
#logging.basicConfig(level=logging.ERROR)

# Constants for portrait folder and max portrait size
PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)

# ─────────────────────────────────────────────────────────────────────────
# CLASS: pcGraphEditor
# A custom graph editor for pcs and factions using CustomTkinter.
# Supports adding nodes, links, dragging, context menus, and saving/loading.
# ─────────────────────────────────────────────────────────────────────────
class PCGraphEditor(ctk.CTkFrame):
    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: __init__
    # Initializes the editor, loads pc data, sets up graph structures, canvas, 
    # scrollbars, and event bindings.
    # ─────────────────────────────────────────────────────────────────────────
    def __init__(self, master, pc_wrapper: GenericModelWrapper, faction_wrapper: GenericModelWrapper, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.selected_shape = None
        self.link_canvas_ids = {}
        self.pc_wrapper = pc_wrapper
        self.faction_wrapper = faction_wrapper
        self.pcs = {pc["Name"]: pc for pc in self.pc_wrapper.load_items()}
        
        # Graph structure to hold nodes and links
        self.graph = {
            "nodes": [],
            "links": [],
            "shapes": []  # 
        }
        self.shapes = {}  # this is for managing shape canvas objects
        self.shape_counter = 0  # if not already added

        # Dictionaries for node data
        self.node_positions = {}  # Current (x, y) positions of nodes
        self.node_images = {}     # Loaded images for node portraits
        self.node_rectangles = {} # Canvas rectangle IDs (for color changes)
        self.node_bboxes = {}     # Bounding boxes for nodes (used for arrow offsets)
        self.shape_counter = 0  # For unique shape tags

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
    # Bind double-click on any PC element to open the editor window
        self.canvas.bind("<Double-Button-1>", self.open_pc_editor)

 # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: open_pc_editor
    # Opens the Generic Editor Window for the clicked pc.
    # ─────────────────────────────────────────────────────────────────────────
    def open_pc_editor(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        pc_tag = next((t for t in tags if t.startswith("pc_")), None)
        if not pc_tag:
            return
        # Convert tag back to pc name (assuming spaces were replaced with underscores)
        pc_name = pc_tag.replace("pc_", "").replace("_", " ")
        pc_item = self.pcs.get(pc_name)
        if not pc_item:
            messagebox.showerror("Error", f"pc '{pc_name}' not found in data.")
            return
        print(f"Opening editor for pc: {pc_name}")
        pc_opener.open_pc_editor_window(pc_name)
        # ─────────────────────────────────────────────────────────────────────────
    def display_portrait_window(self):
        """
        Delegate portrait‐popping to the shared `show_portrait` helper.
        """
        # 1) Validate that an NPC is selected
        node = self.selected_node
        if not node or not node.startswith("npc_"):
            messagebox.showerror("Error", "No NPC selected.")
            return

        # 2) Look up the NPC data
        npc_key = node.replace("npc_", "").replace("_", " ")
        npc_data = self.npcs.get(npc_key)
        if not npc_data:
            messagebox.showerror("Error", f"NPC '{npc_key}' not found.")
            return

        # 3) Grab the portrait path
        portrait_path = npc_data.get("Portrait", "")
        if portrait_path and not os.path.isabs(portrait_path):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
            if os.path.exists(candidate):
                portrait_path = candidate
        if not portrait_path or not os.path.exists(portrait_path):
            messagebox.showerror("Error", "No valid portrait found for this NPC.")
            return

        # 4) Hand off to the shared window
        show_portrait(portrait_path, npc_key)

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
    # Creates a toolbar with buttons for adding pcs, factions, saving, loading, and adding links.
    # ─────────────────────────────────────────────────────────────────────────
    def init_toolbar(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(toolbar, text="Add pc", command=self.add_pc).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Add Faction", command=self.add_faction).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Add Link", command=self.start_link_creation).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Save", command=self.save_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Load", command=self.load_graph).pack(side="left", padx=5)

        # 🆕 Add Shape Buttons
        ctk.CTkButton(toolbar, text="Add Rectangle", command=lambda: self.add_shape("rectangle")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Add Oval", command=lambda: self.add_shape("oval")).pack(side="left", padx=5)
        

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
        self.first_node = next((t for t in tags if t.startswith("pc_")), None)
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
        self.second_node = next((t for t in tags if t.startswith("pc_")), None)
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
            messagebox.showerror("Error", "One or both pcs not found.")
            return
        pc_name1 = tag1.replace("pc_", "").replace("_", " ")
        pc_name2 = tag2.replace("pc_", "").replace("_", " ")
        self.graph["links"].append({
            "pc_name1": pc_name1,
            "pc_name2": pc_name2,
            "text": link_text,
            "arrow_mode": "both"  # Options: "none", "start", "end", "both"
        })
        self.draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_pc
    # Opens an pc selection dialog and binds the next click to place the pc.
    # ─────────────────────────────────────────────────────────────────────────
    def add_pc(self):
        def on_pc_selected(pc_name):
            # Lookup the full pc dictionary using the pc wrapper.
            pc_list = self.pc_wrapper.load_items()
            selected_pc = None
            for pc in pc_list:
                if pc.get("Name") == pc_name:
                    selected_pc = pc
                    break
            if not selected_pc:
                messagebox.showerror("Error", f"pc '{pc_name}' not found.")
                return
            self.pending_pc = selected_pc
            if dialog.winfo_exists():
                dialog.destroy()
            self.canvas.bind("<Button-1>", self.place_pending_pc)

        pc_template = load_template("pcs")
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select pc")
        dialog.geometry("1200x800")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        # The new GenericListSelectionView returns the pc name (string)
        selection_view = GenericListSelectionView(
            dialog,
            "pcs",
            self.pc_wrapper,
            pc_template,
            on_select_callback=lambda et, pc: on_pc_selected(pc)
        )
        selection_view.pack(fill="both", expand=True)
        dialog.wait_window()




    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: place_pending_pc
    # Places the selected pc at the mouse click location and updates the graph.
    # ─────────────────────────────────────────────────────────────────────────
    def place_pending_pc(self, event):
        pc_name = self.pending_pc["Name"]
        tag = f"pc_{pc_name.replace(' ', '_')}"
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.graph["nodes"].append({
            "pc_name": pc_name,
            "x": x,
            "y": y,
            "color": "#1D3572"
        })
        self.node_positions[tag] = (x, y)
        self.pending_pc = None
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.start_drag)
        self.draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: add_faction
    # Opens a faction selection dialog and adds all pcs from the selected faction.
    # ─────────────────────────────────────────────────────────────────────────
    def add_faction(self):
        # Flatten factions from all pcs.
        all_factions = []
        for pc in self.pcs.values():
            faction_value = pc.get("Factions")
            if not faction_value:
                continue
            if isinstance(faction_value, list):
                all_factions.extend(faction_value)
            else:
                all_factions.append(faction_value)
        factions = sorted(set(all_factions))
        if not factions:
            messagebox.showerror("Error", "No factions found in pc data.")
            return

        # Wrap each faction string in a dictionary with a "Name" field.
        items = [{"Name": f} for f in factions]
        # Define a simple template for factions.
        template = {"fields": [{"name": "Name", "type": "text"}]}
        
        # Create a dummy model wrapper that returns our wrapped faction items.
        class DummyModelWrapper:
            def load_items(self):
                return items
        dummy_wrapper = DummyModelWrapper()

        # Define the callback.
        def on_faction_selected(faction_name):
            # Close the selection popup immediately.
            if selection_popup.winfo_exists():
                selection_popup.destroy()
            # Build a list of pcs that have the selected faction.
            faction_pcs = []
            for pc in self.pcs.values():
                faction_value = pc.get("Factions")
                if not faction_value:
                    continue
                if isinstance(faction_value, list):
                    if faction_name in faction_value:
                        faction_pcs.append(pc)
                else:
                    if faction_value == faction_name:
                        faction_pcs.append(pc)
            if not faction_pcs:
                messagebox.showinfo("No pcs", f"No pcs found for faction '{faction_name}'.")
                return
            start_x, start_y = 100, 100
            spacing = 120
            for i, pc in enumerate(faction_pcs):
                pc_name = pc["Name"]
                tag = f"pc_{pc_name.replace(' ', '_')}"
                x = start_x + i * spacing
                y = start_y
                self.graph["nodes"].append({
                    "pc_name": pc_name,
                    "x": x,
                    "y": y,
                    "color": "#1D3572"
                })
                self.node_positions[tag] = (x, y)
            self.draw_graph()

        # Create a new selection popup.
        selection_popup = ctk.CTkToplevel(self)
        selection_popup.title("Select Faction")
        selection_popup.geometry("1200x800")
        selection_popup.transient(self.winfo_toplevel())
        selection_popup.grab_set()
        selection_popup.focus_force()
        
        
        # Instantiate the selection view with our dummy wrapper.
        selection_view = GenericListSelectionView(
            selection_popup,
            "Factions",
            dummy_wrapper,
            template,
            on_select_callback=lambda et, faction: on_faction_selected(faction)
        )
        selection_view.pack(fill="both", expand=True)
        selection_popup.wait_window()

    def update_links_positions_for_node(self, node_tag):
        node_name = node_tag.replace("pc_", "").replace("_", " ")
        for link in self.graph["links"]:
            if node_name in (link["pc_name1"], link["pc_name2"]):
                key = (link["pc_name1"], link["pc_name2"])
                canvas_ids = self.link_canvas_ids.get(key)
                if canvas_ids:
                    tag1 = f"pc_{link['pc_name1'].replace(' ', '_')}"
                    tag2 = f"pc_{link['pc_name2'].replace(' ', '_')}"
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
        node_name = node_tag.replace("pc_", "").replace("_", " ")
        affected_links = [
            link for link in self.graph["links"]
            if link["pc_name1"] == node_name or link["pc_name2"] == node_name
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
        elif any(tag.startswith("pc_") for tag in tags):
            self.selected_node = next((t for t in tags if t.startswith("pc_")), None)
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
            if (link["pc_name1"] == self.selected_link["pc_name1"]
                    and link["pc_name2"] == self.selected_link["pc_name2"]):
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
        node_name = self.selected_node.replace("pc_", "").replace("_", " ")
        self.graph["nodes"] = [node for node in self.graph["nodes"] if node["pc_name"] != node_name]
        self.graph["links"] = [link for link in self.graph["links"]
                               if link["pc_name1"] != node_name and link["pc_name2"] != node_name]
        if self.selected_node in self.node_positions:
            del self.node_positions[self.selected_node]
        self.draw_graph()

    def redraw_after_drag(self):
        self.draw_graph()
        self._redraw_scheduled = False


    # ─────────────────────────────────────────────────────────────────────────
    # FUNCTION: draw_nodes
    # Iterates over all nodes in the graph, draws their rectangles, portraits, and labels,
    # and calculates/stores their bounding boxes.
    # ─────────────────────────────────────────────────────────────────────────
    def draw_nodes(self):
        TEXT_PADDING       = 10
        LINE_SPACING       = 18
        MAX_CHARS_PER_LINE = 50  # you can bump this if you still want some wrapping

        # Create a font object so we can measure pixel widths
        font = Font(family="Arial", size=9)

        for node in self.graph["nodes"]:
            pc_name = node["pc_name"]
            tag     = f"pc_{pc_name.replace(' ', '_')}"

            # ── Normalize Traits ─────────────────────────────────
            raw_traits = self.pcs.get(pc_name, {}).get("Traits", "")
            if isinstance(raw_traits, str):
                trait_text = raw_traits
            elif isinstance(raw_traits, list):
                # each list item is one trait; join with a space so we don't
                # immediately split them on newline
                trait_text = "  ".join(str(item) for item in raw_traits)
            elif isinstance(raw_traits, dict):
                trait_text = raw_traits.get("text", json.dumps(raw_traits))
            else:
                trait_text = str(raw_traits)

            # ── Split only on semicolons (not on newlines!) ───────
            parts = [p.strip() for p in re.split(r";", trait_text) if p.strip()]

            # ── Wrap each part to avoid absurdly long lines ────────
            wrapped = []
            for part in parts:
                lines = textwrap.wrap(part, width=MAX_CHARS_PER_LINE)
                wrapped.extend(lines or [part])

            # ── Build the full list of lines (name, role, traits) ─
            raw_role = self.pcs.get(pc_name, {}).get("Role")
            role     = raw_role.strip() if isinstance(raw_role, str) else ""

            all_lines = [pc_name]
            if role:
                all_lines.append(role)
            all_lines.extend(wrapped)

            # ── Figure out how big it needs to be ───────────────────
            # measure the widest line in pixels
            max_px = max(font.measure(line) for line in all_lines)
            node_w = max_px + 2 * TEXT_PADDING
            node_h = TEXT_PADDING*2 + len(all_lines) * LINE_SPACING

            # positions
            x, y = self.node_positions.get(tag, (node["x"], node["y"]))
            left   = x - node_w/2
            top    = y - node_h/2
            right  = x + node_w/2
            bottom = y + node_h/2

            # ── Draw the rectangle ───────────────────────────────────
            rect_id = self.canvas.create_rectangle(
                left, top, right, bottom,
                fill=node.get("color", "#1D3572"),
                outline="",
                tags=(tag, "node")
            )
            # store for later color‐changes
            self.node_rectangles[tag] = rect_id
            # store for arrow‐head positioning
            self.node_bboxes[tag] = (left, top, right, bottom)

            # ── Draw the text ───────────────────────────────────────
            text_block = "\n".join(all_lines)
            self.canvas.create_text(
                x, top + TEXT_PADDING + LINE_SPACING/2,
                text=text_block,
                fill="white",
                font=("Arial", 9),
                tags=(tag, "node"),
                anchor="n",
                width=node_w - 2*TEXT_PADDING
            )

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
        tag1 = f"pc_{link['pc_name1'].replace(' ', '_')}"
        tag2 = f"pc_{link['pc_name2'].replace(' ', '_')}"
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
        text_id = self.canvas.create_text(mid_x, mid_y,
                                        text=link["text"],
                                        fill="white",
                                        font=("Arial", 10, "bold"),
                                        tags=("link_text",))

        # Store Canvas IDs clearly linked by pc pair
        key = (link["pc_name1"], link["pc_name2"])
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
                tag = f"pc_{node['pc_name'].replace(' ', '_')}"
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
    def load_graph(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                self.graph = json.load(f)
            if "shapes" not in self.graph:
                self.graph["shapes"] = []
            
            # Reload node positions and links as before...
            self.node_positions = {
                f"pc_{n['pc_name'].replace(' ', '_')}": (n["x"], n["y"])
                for n in self.graph["nodes"]
            }
            for node in self.graph["nodes"]:
                node["color"] = "#1D3572"
            for link in self.graph["links"]:
                link["arrow_mode"] = link.get("arrow_mode", "both")
            
            # Rebuild shapes from saved data.
            self.shapes.clear()
            # Sort shapes by their z-order so that lower ones are drawn first.
            shapes_sorted = sorted(self.graph.get("shapes", []), key=lambda s: s.get("z", 0))
            for shape in shapes_sorted:
                self.shapes[shape["tag"]] = shape
            
            # Update shape_counter so that new shapes will have unique tags.
            max_counter = -1
            for shape in self.graph["shapes"]:
                try:
                    # Assume tag format is "shape_<number>"
                    num = int(shape["tag"].split("_")[1])
                    if num > max_counter:
                        max_counter = num
                except (IndexError, ValueError):
                    pass
            self.shape_counter = max_counter + 1

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
                if node["pc_name"] == self.selected_node.replace("pc_", "").replace("_", " "):
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
        shape_menu.add_command(label="Send to Back", command=lambda: self.send_to_back(shape_tag))  
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

    def send_to_back(self, shape_tag):
        # Lower the shape on the canvas.
        self.canvas.tag_lower(shape_tag)
        shape = self.shapes.get(shape_tag)
        if shape:
            # Set the shape's z property to a value lower than all others.
            min_z = min((s.get("z", 0) for s in self.shapes.values()), default=0)
            shape["z"] = min_z - 1
            self.graph["shapes"].sort(key=lambda s: s.get("z", 0))

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
            pc_name1 = link["pc_name1"]
            pc_name2 = link["pc_name2"]
            tag1 = f"pc_{pc_name1.replace(' ', '_')}"
            tag2 = f"pc_{pc_name2.replace(' ', '_')}"
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
        x, y, w, h = shape["x"], shape["y"], shape["w"], shape["h"]
        left = x - w//2
        top = y - h//2
        right = x + w//2
        bottom = y + h//2
        tag = shape["tag"]
        if shape["type"] == "rectangle":
            shape_id = self.canvas.create_rectangle(left, top, right, bottom, fill=shape["color"], tags=(tag, "shape"))
        else:
            shape_id = self.canvas.create_oval(left, top, right, bottom, fill=shape["color"], tags=(tag, "shape"))
        shape["canvas_id"] = shape_id

    def draw_all_shapes(self):
        # Sort shapes based on the stored z-index.
        shapes_sorted = sorted(self.graph.get("shapes", []), key=lambda s: s.get("z", 0))
        for shape in shapes_sorted:
            self.shapes[shape["tag"]] = shape
            self.draw_shape(shape)

    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json")
        if file_path:
            # Save node positions, etc.
            for node in self.graph["nodes"]:
                tag = f"pc_{node['pc_name'].replace(' ', '_')}"
                x, y = self.node_positions.get(tag, (node["x"], node["y"]))
                node["x"] = x
                node["y"] = y

            for link in self.graph["links"]:
                if "arrow_mode" not in link:
                    link["arrow_mode"] = "both"

            # Update each shape's data.
            for shape in self.graph.get("shapes", []):
                tag = shape["tag"]
                if tag in self.shapes:
                    shape_obj = self.shapes[tag]
                    shape["x"] = shape_obj["x"]
                    shape["y"] = shape_obj["y"]
                    shape["w"] = shape_obj["w"]
                    shape["h"] = shape_obj["h"]
                    shape["z"] = shape_obj.get("z", 0)
                    shape.pop("canvas_id", None)
                    shape.pop("resize_handle", None)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.graph, f, indent=2)

    def draw_graph(self):
        self.canvas.delete("all")
        self.node_images.clear()
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
        if self.canvas.find_withtag("link"):
            self.canvas.tag_lower("node", "link")
        else:
            self.canvas.tag_lower("node")
        # Lower "shape" below "link" if possible.
        if self.canvas.find_withtag("shape") and self.canvas.find_withtag("link"):
            self.canvas.tag_lower("shape", "link")
        elif self.canvas.find_withtag("shape"):
            self.canvas.tag_lower("shape")


    def start_drag(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        self.selected_node = next((t for t in tags if t.startswith("pc_")), None)
        self.selected_shape = next((t for t in tags if t.startswith("shape_")), None)
        self.selected_items = self.canvas.find_withtag(self.selected_node or self.selected_shape)
        self.drag_start = (x, y)

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
