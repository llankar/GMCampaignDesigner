import tkinter as tk
import customtkinter as ctk
from modules.ui.icon_button import create_icon_button
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

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
        "marker":    self.load_icon("assets/icons/marker.png",       (48,48)),
    }

    # Fog controls
    self._fog_button_default_style = {
        "fg_color": "#0077CC",
        "hover_color": "#005fa3",
        "border_color": "#005fa3",
    }
    self._fog_button_active_style = {
        "fg_color": "#004c80",
        "hover_color": "#004c80",
        "border_color": "#33a8ff",
    }
    self._fog_buttons = {}

    add_fog_container = create_icon_button(
        toolbar,
        icons["add"],
        "Add Fog",
        command=lambda: self._set_fog("add")
    )
    add_fog_container.pack(side="left")
    self._fog_buttons["add"] = getattr(add_fog_container, "button", None)

    rem_fog_container = create_icon_button(
        toolbar,
        icons["rem"],
        "Remove Fog",
        command=lambda: self._set_fog("rem")
    )
    rem_fog_container.pack(side="left")
    self._fog_buttons["rem"] = getattr(rem_fog_container, "button", None)

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
    create_icon_button(toolbar, icons["marker"], "Add Marker", command=self.add_marker)\
        .pack(side="left", padx=2)
    create_icon_button(toolbar, icons["fs"],    "Fullscreen",   command=self.open_fullscreen)\
        .pack(side="left", padx=2)
    create_icon_button(toolbar, icons["fs"],    "Web Display",   command=self.open_web_display)\
        .pack(side="left", padx=2)

    # Brush shape selector (for fog)
    shape_label = ctk.CTkLabel(toolbar, text="Fog Shape:") # Clarified label
    shape_label.pack(side="left", padx=(10,2), pady=8)
    dropdown_width = 100

    self.shape_menu = ctk.CTkOptionMenu(
        toolbar,
        values=["Rectangle", "Circle"],
        command=self._on_brush_shape_change, # This is for fog brush shape
        width=dropdown_width,
    )
    self.shape_menu.set("Rectangle") # Default fog brush shape
    self.shape_menu.pack(side="left", padx=5, pady=8)

    # Brush‐size control in dark mode (for fog)
    size_label = ctk.CTkLabel(toolbar, text="Fog Brush Size:") # Clarified label
    size_label.pack(side="left", padx=(10,2), pady=8)

    brush_size_options = list(getattr(self, "brush_size_options", list(range(4, 129, 4))))
    current_brush_size = int(getattr(self, "brush_size", brush_size_options[0] if brush_size_options else 32))
    if current_brush_size not in brush_size_options:
        brush_size_options.append(current_brush_size)
        brush_size_options = sorted(set(brush_size_options))
    self.brush_size_options = list(brush_size_options)
    brush_size_values = [str(size) for size in self.brush_size_options]
    self.brush_size_menu = ctk.CTkOptionMenu(
        toolbar,
        values=brush_size_values,
        command=self._on_brush_size_change, # This is for fog brush size
        width=dropdown_width,
    )
    self.brush_size_menu.set(str(current_brush_size))
    self.brush_size_menu.pack(side="left", padx=5, pady=8)

    # Key bindings for bracket adjustments (for fog brush)
    self.parent.bind("[", lambda e: self._change_brush(-4))
    self.parent.bind("]", lambda e: self._change_brush(+4))

    # Token‐size control
    token_size_label = ctk.CTkLabel(toolbar, text="Token Size:") # Renamed label variable
    token_size_label.pack(side="left", padx=(10,2), pady=8)

    token_size_options = list(getattr(self, "token_size_options", list(range(16, 129, 8))))
    current_token_size = int(getattr(self, "token_size", token_size_options[0] if token_size_options else 48))
    if current_token_size not in token_size_options:
        token_size_options.append(current_token_size)
        token_size_options = sorted(set(token_size_options))
    self.token_size_options = list(token_size_options)
    token_size_values = [str(size) for size in self.token_size_options]
    self.token_size_menu = ctk.CTkOptionMenu(
        toolbar,
        values=token_size_values,
        command=self._on_token_size_change,
        width=dropdown_width,
    )
    self.token_size_menu.set(str(current_token_size))
    self.token_size_menu.pack(side="left", padx=5, pady=8)
    
    self.token_size_value_label = ctk.CTkLabel(
        toolbar,
        text=str(self.token_size),
        width=32
    )
    self.token_size_value_label.pack(side="left", padx=(2,10), pady=8)

    # Info card font size selector
    hover_font_label = ctk.CTkLabel(toolbar, text="Info Card Font Size:")
    hover_font_label.pack(side="left", padx=(10,2), pady=8)

    font_sizes = getattr(self, "hover_font_size_options", [10, 12, 14, 16, 18, 20, 24, 28, 32])
    current_hover_size = getattr(self, "hover_font_size", 14)
    if current_hover_size not in font_sizes:
        font_sizes = sorted(set(list(font_sizes) + [current_hover_size]))
    self.hover_font_size_options = list(font_sizes)
    font_size_values = [str(size) for size in self.hover_font_size_options]
    self.hover_font_size_menu = ctk.CTkOptionMenu(
        toolbar,
        values=font_size_values,
        command=self._on_hover_font_size_change,
        width=dropdown_width,
    )
    self.hover_font_size_menu.set(str(current_hover_size))
    self.hover_font_size_menu.pack(side="left", padx=5, pady=8)

    # --- Drawing Tool Selector ---
    tool_label = ctk.CTkLabel(toolbar, text="Active Tool:")
    tool_label.pack(side="left", padx=(20,2), pady=8)
    self.drawing_tool_menu = ctk.CTkOptionMenu(
        toolbar,
        values=["Token", "Rectangle", "Oval"],
        command=self._on_drawing_tool_change, # To be created in DisplayMapController
        width=dropdown_width,
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
        command=self._on_shape_fill_mode_change, # To be created in DisplayMapController
        width=dropdown_width,
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

    self._update_fog_button_states()

def _on_brush_size_change(self, val): # This is for FOG brush
    try:
        size = int(val)
    except (TypeError, ValueError):
        return
    self.brush_size = size
    options = list(getattr(self, "brush_size_options", []))
    if size not in options:
        options.append(size)
        options = sorted(set(options))
        menu = getattr(self, "brush_size_menu", None)
        if menu:
            try:
                menu.configure(values=[str(v) for v in options])
            except tk.TclError:
                pass
    self.brush_size_options = list(options)

def _on_brush_shape_change(self, val): # This is for FOG brush
    # normalize to lowercase for comparisons
    self.brush_shape = val.lower()

def _change_brush(self, delta): # This is for FOG brush
    options = list(getattr(self, "brush_size_options", list(range(4, 129, 4))))
    if not options:
        return
    min_size = min(options)
    max_size = max(options)
    new = max(min_size, min(max_size, self.brush_size + delta))
    self._on_brush_size_change(new)
    menu = getattr(self, "brush_size_menu", None)
    if menu:
        try:
            menu.set(str(self.brush_size))
        except tk.TclError:
            pass

def _on_token_size_change(self, val):
    try:
        size = int(val)
    except (TypeError, ValueError):
        return
    self.token_size = size
    options = list(getattr(self, "token_size_options", []))
    if size not in options:
        options.append(size)
        options = sorted(set(options))
        menu = getattr(self, "token_size_menu", None)
        if menu:
            try:
                menu.configure(values=[str(v) for v in options])
            except tk.TclError:
                pass
    self.token_size_options = list(options)
    if hasattr(self, 'token_size_value_label'): # Check if label exists
        try:
            self.token_size_value_label.configure(text=str(self.token_size))
        except tk.TclError:
            pass


def _update_fog_button_states(self):
    """Update fog button appearance to reflect the active fog tool."""
    buttons = getattr(self, "_fog_buttons", {})
    default_style = getattr(self, "_fog_button_default_style", {})
    active_style = getattr(self, "_fog_button_active_style", {})
    active_mode = getattr(self, "fog_mode", None)

    for mode, button in buttons.items():
        if not button:
            continue
        style = active_style if mode == active_mode else default_style
        try:
            button.configure(**style)
        except tk.TclError:
            # If the button has been destroyed, ignore the update.
            continue

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
