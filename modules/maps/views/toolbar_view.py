import tkinter as tk
import customtkinter as ctk
from modules.ui.icon_button import create_icon_button
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

def _build_toolbar(self):
    def _create_collapsible_section(parent, title):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(side="left", padx=6, pady=2, fill="y")

        toggle_state = tk.BooleanVar(value=True)
        content_frame = ctk.CTkFrame(section, fg_color="transparent")
        content_frame.pack(side="left", fill="y")

        def _toggle():
            if toggle_state.get():
                content_frame.pack_forget()
                toggle_state.set(False)
                toggle_button.configure(text=f"{title} ▶")
            else:
                content_frame.pack(side="left", fill="y")
                toggle_state.set(True)
                toggle_button.configure(text=f"{title} ▼")

        toggle_button = ctk.CTkButton(
            section,
            text=f"{title} ▼",
            command=_toggle,
            width=120,
            height=48,
        )
        toggle_button.pack(side="left", padx=(0, 6), pady=4)
        return content_frame

    # Main toolbar container that fills the width and holds the scrollable area
    toolbar_container = ctk.CTkFrame(self.parent)
    toolbar_container.pack(side="top", fill="x", pady=(0,2)) # Added small pady for visual separation
    # Expose on controller for downstream layout sizing
    try:
        self._toolbar_container = toolbar_container
    except Exception:
        pass

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
        "chatbot":    self.load_icon("assets/icons/chatbot.png",       (48,48)),

    }

    dropdown_width = 100

    # Fog controls
    fog_section = _create_collapsible_section(toolbar, "Fog")
    self._fog_button_default_style = {
        "fg_color": "#0077CC",
        "hover_color": "#005fa3",
        "border_color": "#005fa3",
        "border_width": 1,
    }
    self._fog_button_active_style = {
        "fg_color": "#004c80",
        "hover_color": "#004c80",
        "border_color": "#d7263d",
        "border_width": 3,
    }
    self._fog_buttons = {}

    add_fog_container = create_icon_button(
        fog_section,
        icons["add"],
        "Add Fog",
        command=lambda: self._set_fog("add")
    )
    add_fog_container.pack(side="left")
    self._fog_buttons["add"] = getattr(add_fog_container, "button", None)

    rem_fog_container = create_icon_button(
        fog_section,
        icons["rem"],
        "Remove Fog",
        command=lambda: self._set_fog("rem")
    )
    rem_fog_container.pack(side="left")
    self._fog_buttons["rem"] = getattr(rem_fog_container, "button", None)

    add_rect_container = create_icon_button(
        fog_section,
        icons["add"],
        "Add Fog Rectangle",
        command=lambda: self._set_fog("add_rect")
    )
    add_rect_container.pack(side="left")
    self._fog_buttons["add_rect"] = getattr(add_rect_container, "button", None)

    rem_rect_container = create_icon_button(
        fog_section,
        icons["rem"],
        "Remove Fog Rectangle",
        command=lambda: self._set_fog("rem_rect")
    )
    rem_rect_container.pack(side="left")
    self._fog_buttons["rem_rect"] = getattr(rem_rect_container, "button", None)

    create_icon_button(fog_section, icons["clear"], "Clear Fog",   command=self.clear_fog).pack(side="left")
    create_icon_button(fog_section, icons["reset"], "Reset Fog",   command=self.reset_fog).pack(side="left")

    shape_label = ctk.CTkLabel(fog_section, text="Fog Shape:") # Clarified label
    shape_label.pack(side="left", padx=(10,2), pady=8)

    self.shape_menu = ctk.CTkOptionMenu(
        fog_section,
        values=["Rectangle", "Circle"],
        command=self._on_brush_shape_change, # This is for fog brush shape
        width=dropdown_width,
    )
    self.shape_menu.set("Rectangle") # Default fog brush shape
    self.shape_menu.pack(side="left", padx=5, pady=8)

    size_label = ctk.CTkLabel(fog_section, text="Fog Brush Size:") # Clarified label
    size_label.pack(side="left", padx=(2,2), pady=8)

    brush_size_options = list(getattr(self, "brush_size_options", list(range(4, 129, 4))))
    current_brush_size = int(getattr(self, "brush_size", brush_size_options[0] if brush_size_options else 32))
    if current_brush_size not in brush_size_options:
        brush_size_options.append(current_brush_size)
        brush_size_options = sorted(set(brush_size_options))
    self.brush_size_options = list(brush_size_options)
    brush_size_values = [str(size) for size in self.brush_size_options]
    self.brush_size_menu = ctk.CTkOptionMenu(
        fog_section,
        values=brush_size_values,
        command=self._on_brush_size_change, # This is for fog brush size
        width=dropdown_width,
    )
    self.brush_size_menu.set(str(current_brush_size))
    self.brush_size_menu.pack(side="left", padx=0, pady=5)

    # Key bindings for bracket adjustments (for fog brush)
    self.parent.bind("[", lambda e: self._change_brush(-4))
    self.parent.bind("]", lambda e: self._change_brush(+4))

    # Token controls and fullscreen before the brush size
    token_section = _create_collapsible_section(toolbar, "Tokens")
    create_icon_button(token_section, icons["creat"], "Add Creature", command=lambda: self.open_entity_picker("Creature"))\
        .pack(side="left", padx=2)
    create_icon_button(token_section, icons["npc"],   "Add NPC",      command=lambda: self.open_entity_picker("NPC"))\
        .pack(side="left", padx=2)
    create_icon_button(token_section, icons["pc"], "Add PC", command=lambda: self.open_entity_picker("PC")) \
        .pack(side="left", padx=2)
    create_icon_button(token_section, icons["marker"], "Add Marker", command=self.add_marker)\
        .pack(side="left", padx=2)

    token_size_label = ctk.CTkLabel(token_section, text="Token Size:") # Renamed label variable
    token_size_label.pack(side="left", padx=(10,2), pady=8)

    token_size_options = list(getattr(self, "token_size_options", list(range(16, 129, 8))))
    current_token_size = int(getattr(self, "token_size", token_size_options[0] if token_size_options else 48))
    if current_token_size not in token_size_options:
        token_size_options.append(current_token_size)
        token_size_options = sorted(set(token_size_options))
    self.token_size_options = list(token_size_options)
    token_size_values = [str(size) for size in self.token_size_options]
    self.token_size_menu = ctk.CTkOptionMenu(
        token_section,
        values=token_size_values,
        command=self._on_token_size_change,
        width=dropdown_width,
    )
    self.token_size_menu.set(str(current_token_size))
    self.token_size_menu.pack(side="left", padx=5, pady=8)

    drawing_section = _create_collapsible_section(toolbar, "Drawing / Whiteboard")
    # --- Drawing Tool Selector ---
    tool_label = ctk.CTkLabel(drawing_section, text="Active Tool:")
    tool_label.pack(side="left", padx=(10,2), pady=8)
    drawing_tools = ["Token", "Rectangle", "Oval", "Whiteboard", "Eraser"]
    self.drawing_tool_menu = ctk.CTkOptionMenu(
        drawing_section,
        values=drawing_tools,
        command=self._on_drawing_tool_change, # To be created in DisplayMapController
        width=dropdown_width,
    )
    # Ensure self.drawing_mode is initialized in DisplayMapController before this
    self.drawing_tool_menu.set(self.drawing_mode.capitalize() if hasattr(self, 'drawing_mode') else "Token")
    self.drawing_tool_menu.pack(side="left", padx=5, pady=8)

    whiteboard_controls = ctk.CTkFrame(drawing_section, fg_color="transparent")
    whiteboard_controls.pack(side="left", padx=(8, 2), pady=4)
    self.whiteboard_controls_frame = whiteboard_controls

    self.whiteboard_color_button = ctk.CTkButton(
        whiteboard_controls,
        text="Ink Color",
        width=90,
        command=self._on_pick_whiteboard_color,
    )
    try:
        self.whiteboard_color_button.configure(fg_color=getattr(self, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    self.whiteboard_color_button.pack(side="left", padx=(0, 6), pady=6)

    width_container = ctk.CTkFrame(whiteboard_controls, fg_color="transparent")
    width_container.pack(side="left", padx=(0, 6), pady=6)
    width_label = ctk.CTkLabel(width_container, text="Width")
    width_label.pack(side="left", padx=(0, 4))
    self.whiteboard_width_slider = ctk.CTkSlider(
        width_container,
        from_=1,
        to=20,
        number_of_steps=19,
        command=self._on_whiteboard_width_change,
        width=120,
    )
    current_width = float(getattr(self, "whiteboard_width", 4))
    self.whiteboard_width_slider.set(current_width)
    width_value_label = ctk.CTkLabel(width_container, text=str(int(current_width)))
    width_value_label.pack(side="left", padx=(6, 0))
    self.whiteboard_width_value_label = width_value_label

    eraser_controls = ctk.CTkFrame(drawing_section, fg_color="transparent")
    eraser_controls.pack(side="left", padx=(8, 2), pady=4)
    self.eraser_controls_frame = eraser_controls

    eraser_width_container = ctk.CTkFrame(eraser_controls, fg_color="transparent")
    eraser_width_container.pack(side="left", padx=(0, 6), pady=6)
    eraser_label = ctk.CTkLabel(eraser_width_container, text="Eraser Radius")
    eraser_label.pack(side="left", padx=(0, 4))
    self.whiteboard_eraser_slider = ctk.CTkSlider(
        eraser_width_container,
        from_=2,
        to=40,
        number_of_steps=38,
        command=self._on_eraser_radius_change,
        width=120,
    )
    eraser_width = float(getattr(self, "whiteboard_eraser_radius", 8))
    self.whiteboard_eraser_slider.set(eraser_width)
    eraser_value_label = ctk.CTkLabel(eraser_width_container, text=str(int(eraser_width)))
    eraser_value_label.pack(side="left", padx=(6, 0))
    self.eraser_radius_value_label = eraser_value_label

    # --- Shape Fill Mode Selector (conditionally visible) ---
    self.shape_fill_label = ctk.CTkLabel(drawing_section, text="Shape Fill:")
    # Packed by _update_shape_controls_visibility
    self.shape_fill_mode_menu = ctk.CTkOptionMenu(
        drawing_section,
        values=["Filled", "Border Only"],
        command=self._on_shape_fill_mode_change, # To be created in DisplayMapController
        width=dropdown_width,
    )
    # Ensure self.shape_is_filled is initialized
    self.shape_fill_mode_menu.set("Filled" if hasattr(self, 'shape_is_filled') and self.shape_is_filled else "Border Only")
    # Packed by _update_shape_controls_visibility

    # --- Shape Color Pickers (conditionally visible) ---
    self.shape_fill_color_button = ctk.CTkButton(
        drawing_section,
        text="Fill Color",
        width=80,
        command=self._on_pick_shape_fill_color # To be created in DisplayMapController
    )
    # Packed by _update_shape_controls_visibility

    self.shape_border_color_button = ctk.CTkButton(
        drawing_section,
        text="Border Color",
        width=100,
        command=self._on_pick_shape_border_color # To be created in DisplayMapController
    )
    # Packed by _update_shape_controls_visibility

    display_section = _create_collapsible_section(toolbar, "Display")
    create_icon_button(display_section, icons["save"],  "Save Map",    command=self.save_map).pack(side="left")
    create_icon_button(display_section, icons["fs"],    "Fullscreen",   command=self.open_fullscreen)\
        .pack(side="left", padx=2)
    create_icon_button(display_section, icons["fs"],    "Web Display",   command=self.open_web_display)\
        .pack(side="left", padx=2)
    create_icon_button(display_section, icons["chatbot"],    "Chatbot",   command=self.open_chatbot_assistant)\
        .pack(side="left", padx=2)

    hover_font_label = ctk.CTkLabel(display_section, text="Info Card Font Size:")
    hover_font_label.pack(side="left", padx=(10,2), pady=8)

    font_sizes = getattr(self, "hover_font_size_options", [10, 12, 14, 16, 18, 20, 24, 28, 32])
    current_hover_size = getattr(self, "hover_font_size", 14)
    if current_hover_size not in font_sizes:
        font_sizes = sorted(set(list(font_sizes) + [current_hover_size]))
    self.hover_font_size_options = list(font_sizes)
    font_size_values = [str(size) for size in self.hover_font_size_options]
    self.hover_font_size_menu = ctk.CTkOptionMenu(
        display_section,
        values=font_size_values,
        command=self._on_hover_font_size_change,
        width=dropdown_width,
    )
    self.hover_font_size_menu.set(str(current_hover_size))
    self.hover_font_size_menu.pack(side="left", padx=5, pady=8)

    # --- Fit Mode selector ---
    fit_label = ctk.CTkLabel(display_section, text="Fit:")
    fit_label.pack(side="left", padx=(14,2), pady=8)
    fit_values = ["Contain", "Width", "Height"]
    current_fit = getattr(self, "fit_mode", "Contain")
    if current_fit not in fit_values:
        current_fit = "Contain"
    self.fit_mode_menu = ctk.CTkOptionMenu(
        display_section,
        values=fit_values,
        command=getattr(self, "_on_fit_mode_change", None) or (lambda _v: None),
        width=dropdown_width,
    )
    self.fit_mode_menu.set(current_fit)
    self.fit_mode_menu.pack(side="left", padx=5, pady=8)

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
