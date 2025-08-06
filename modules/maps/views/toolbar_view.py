import tkinter as tk
import customtkinter as ctk
from modules.ui.icon_button import create_icon_button

def _build_toolbar(self):    
    # Main toolbar container that fills the width and holds the scrollable area
    toolbar_container = ctk.CTkFrame(self.parent)
    toolbar_container.pack(side="top", fill="x", pady=(0,2)) # Added small pady for visual separation

    # Scrollable frame for the actual toolbar content
    # Set a fixed height for the scrollable area, width will be determined by content
    # The scrollbar will appear automatically if content width exceeds available width.
    toolbar_height = 65 # Adjust as needed for your icon/widget sizes
    toolbar = ctk.CTkScrollableFrame(toolbar_container, orientation="horizontal", height=toolbar_height)
    toolbar.pack(fill="x", expand=True) # Make the scrollable area fill the container

    # Load icons
    icons = {
        "add":   self.load_icon("assets/icons/brush.png",    (48,48)),
        "rem":   self.load_icon("assets/icons/eraser.png",   (48,48)),
        "clear": self.load_icon("assets/icons/empty.png",    (48,48)),
        "reset": self.load_icon("assets/icons/full.png",     (48,48)),
        "save":  self.load_icon("assets/icons/save.png",     (48,48)),
        "fs":    self.load_icon("assets/icons/expand.png",   (48,48)),
        "npc":   self.load_icon("assets/icons/npc.png",      (48,48)),
        "creat": self.load_icon("assets/icons/creature.png", (48,48)),
        "pc":    self.load_icon("assets/icons/pc.png",       (48,48)),
    }

    # Fog controls
    create_icon_button(toolbar, icons["add"],   "Add Fog",     command=lambda: self._set_fog("add")).pack(side="left")
    create_icon_button(toolbar, icons["rem"],   "Remove Fog",  command=lambda: self._set_fog("rem")).pack(side="left")
    create_icon_button(toolbar, icons["clear"], "Clear Fog",   command=self.clear_fog).pack(side="left")
    create_icon_button(toolbar, icons["reset"], "Reset Fog",   command=self.reset_fog).pack(side="left")
    create_icon_button(toolbar, icons["save"],  "Save Map",    command=self.save_map).pack(side="left")

    # Token controls and fullscreen before the brush size
    create_icon_button(toolbar, icons["creat"], "Add Creature", command=lambda: self.open_entity_picker("Creature"))\
        .pack(side="left", padx=2)
    create_icon_button(toolbar, icons["npc"],   "Add NPC",      command=lambda: self.open_entity_picker("NPC"))\
        .pack(side="left", padx=2)
    create_icon_button(toolbar, icons["pc"], "Add PC", command=lambda: self.open_entity_picker("PC")) \
        .pack(side="left", padx=2)
    create_icon_button(toolbar, icons["fs"],    "Fullscreen",   command=self.open_fullscreen)\
        .pack(side="left", padx=2)
    create_icon_button(toolbar, icons["fs"],    "Web Display",   command=self.open_web_display)\
        .pack(side="left", padx=2)

    # Brush shape selector (for fog)
    shape_label = ctk.CTkLabel(toolbar, text="Fog Shape:") # Clarified label
    shape_label.pack(side="left", padx=(10,2), pady=8)
    self.shape_menu = ctk.CTkOptionMenu(
        toolbar,
        values=["Rectangle", "Circle"],
        command=self._on_brush_shape_change # This is for fog brush shape
    )
    self.shape_menu.set("Rectangle") # Default fog brush shape
    self.shape_menu.pack(side="left", padx=5, pady=8)

    # Brush‐size control in dark mode (for fog)
    size_label = ctk.CTkLabel(toolbar, text="Fog Brush Size:") # Clarified label
    size_label.pack(side="left", padx=(10,2), pady=8)
    self.brush_slider = ctk.CTkSlider(
        toolbar, from_=4, to=128,
        command=self._on_brush_size_change # This is for fog brush size
    )
    self.brush_slider.set(self.brush_size)
    self.brush_slider.pack(side="left", padx=5, pady=8)

    # Key bindings for bracket adjustments (for fog brush)
    self.parent.bind("[", lambda e: self._change_brush(-4))
    self.parent.bind("]", lambda e: self._change_brush(+4))

    # Token‐size control
    token_size_label = ctk.CTkLabel(toolbar, text="Token Size:") # Renamed label variable
    token_size_label.pack(side="left", padx=(10,2), pady=8)

    self.token_slider = ctk.CTkSlider(
        toolbar, from_=16, to=128,
        command=self._on_token_size_change
    )
    self.token_slider.set(self.token_size)
    self.token_slider.pack(side="left", padx=5, pady=8)
    
    self.token_size_value_label = ctk.CTkLabel(
        toolbar,
        text=str(self.token_size),
        width=32
    )
    self.token_size_value_label.pack(side="left", padx=(2,10), pady=8)

    # --- Drawing Tool Selector ---
    tool_label = ctk.CTkLabel(toolbar, text="Active Tool:")
    tool_label.pack(side="left", padx=(20,2), pady=8)
    self.drawing_tool_menu = ctk.CTkOptionMenu(
        toolbar,
        values=["Token", "Rectangle", "Oval"],
        command=self._on_drawing_tool_change # To be created in DisplayMapController
    )
    # Ensure self.drawing_mode is initialized in DisplayMapController before this
    self.drawing_tool_menu.set(self.drawing_mode.capitalize() if hasattr(self, 'drawing_mode') else "Token")
    self.drawing_tool_menu.pack(side="left", padx=5, pady=8)

    # --- Shape Fill Mode Selector (conditionally visible) ---
    self.shape_fill_label = ctk.CTkLabel(toolbar, text="Shape Fill:")
    # Packed by _update_shape_controls_visibility
    self.shape_fill_mode_menu = ctk.CTkOptionMenu(
        toolbar,
        values=["Filled", "Border Only"],
        command=self._on_shape_fill_mode_change # To be created in DisplayMapController
    )
    # Ensure self.shape_is_filled is initialized
    self.shape_fill_mode_menu.set("Filled" if hasattr(self, 'shape_is_filled') and self.shape_is_filled else "Border Only")
    # Packed by _update_shape_controls_visibility

    # --- Shape Color Pickers (conditionally visible) ---
    self.shape_fill_color_button = ctk.CTkButton(
        toolbar,
        text="Fill Color",
        width=80,
        command=self._on_pick_shape_fill_color # To be created in DisplayMapController
    )
    # Packed by _update_shape_controls_visibility

    self.shape_border_color_button = ctk.CTkButton(
        toolbar,
        text="Border Color",
        width=100,
        command=self._on_pick_shape_border_color # To be created in DisplayMapController
    )
    # Packed by _update_shape_controls_visibility
    
    # Initial visibility update for shape controls (call method on self)
    if hasattr(self, '_update_shape_controls_visibility'):
        self._update_shape_controls_visibility()

def _on_brush_size_change(self, val): # This is for FOG brush
    try:
        self.brush_size = int(val)
    except ValueError:
        pass

def _on_brush_shape_change(self, val): # This is for FOG brush
    # normalize to lowercase for comparisons
    self.brush_shape = val.lower()

def _change_brush(self, delta): # This is for FOG brush
    new = max(4, min(128, self.brush_size + delta))
    self.brush_size = new
    self.brush_slider.set(new)

def _on_token_size_change(self, val):
    try:
        self.token_size = int(val)
        if hasattr(self, 'token_size_value_label'): # Check if label exists
            self.token_size_value_label.configure(text=str(self.token_size))
    except ValueError:
        pass

# Placeholder for new callbacks in DisplayMapController - these will be defined there.
# def _on_drawing_tool_change(self, selected_tool):
#     self.drawing_mode = selected_tool.lower()
#     self._update_shape_controls_visibility()

# def _on_shape_fill_mode_change(self, selected_mode):
#     self.shape_is_filled = (selected_mode == "Filled")

# def _on_pick_shape_fill_color(self):
#     # Opens color chooser and updates self.current_shape_fill_color
#     pass 

# def _on_pick_shape_border_color(self):
#     # Opens color chooser and updates self.current_shape_border_color
#     pass

# def _update_shape_controls_visibility(self):
#  if self.drawing_mode in ["rectangle", "oval"]:
#      self.shape_fill_label.pack(side="left", padx=(10,2), pady=8)
#      self.shape_fill_mode_menu.pack(side="left", padx=5, pady=8)
#      self.shape_fill_color_button.pack(side="left", padx=(10,2), pady=8)
#      self.shape_border_color_button.pack(side="left", padx=2, pady=8)
#  else:
#      self.shape_fill_label.pack_forget()
#      self.shape_fill_mode_menu.pack_forget()
#      self.shape_fill_color_button.pack_forget()
#      self.shape_border_color_button.pack_forget()
