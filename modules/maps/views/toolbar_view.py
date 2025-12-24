import tkinter as tk
import customtkinter as ctk
from modules.ui.icon_dropdown import IconDropdown
from modules.helpers.logging_helper import log_module_import
from modules.scenarios.plot_twist_panel import (
    add_plot_twist_listener,
    get_latest_plot_twist,
    remove_plot_twist_listener,
    roll_plot_twist,
)

log_module_import(__name__)

def _build_toolbar(self):
    section_tracker = {"count": 0}
    horizontal_spacing = 4
    control_pady = 4

    def _pack_control(widget, *, leading=0, trailing=None, pady=None):
        padx = (leading, horizontal_spacing if trailing is None else trailing)
        widget.pack(side="left", padx=padx, pady=control_pady if pady is None else pady)

    def _create_collapsible_section(parent, title):
        if section_tracker["count"]:
            separator = ctk.CTkFrame(
                parent,
                fg_color="#3a3a3a",
                width=2,
                corner_radius=2,
            )
            separator.pack(side="left", fill="y", padx=(4, 8), pady=(4, 4))

        section_tracker["count"] += 1

        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(side="left", padx=(0, 8), pady=2, fill="y")

        toggle_state = tk.BooleanVar(value=True)
        def _toggle():
            if toggle_state.get():
                content_frame.pack_forget()
                toggle_state.set(False)
                toggle_button.configure(text=f"{title} ▶")
            else:
                content_frame.pack(side="left", fill="y", padx=(0, 4), pady=(2, 2))
                toggle_state.set(True)
                toggle_button.configure(text=f"{title} ▼")

        toggle_button = ctk.CTkButton(
            section,
            text=f"{title} ▼",
            command=_toggle,
            width=82,
            height=30,
        )
        toggle_button.pack(side="left", padx=(0, 4), pady=4)

        content_frame = ctk.CTkFrame(
            section,
            fg_color="#101010",
            border_width=1,
            border_color="#404040",
            corner_radius=8,
        )
        content_frame.pack(side="left", fill="y", padx=(0, 4), pady=(2, 2))
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
        "rotate":    self.load_icon("assets/icons/turn_background_icon.png",   (48,48)),
        "npc":   self.load_icon("assets/icons/npc.png",      (48,48)),
        "creat": self.load_icon("assets/icons/creature.png", (48,48)),
        "pc":    self.load_icon("assets/icons/pc.png",       (48,48)),
        "marker":    self.load_icon("assets/icons/marker.png",       (48,48)),
        "chatbot":    self.load_icon("assets/icons/chatbot.png",       (48,48)),

    }

    dropdown_width = 0

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

    fog_actions = [
        {"key": "add", "icon": icons["add"], "tooltip": "Add Fog", "command": lambda: self._set_fog("add")},
        {"key": "rem", "icon": icons["rem"], "tooltip": "Remove Fog", "command": lambda: self._set_fog("rem")},
        {"key": "add_rect", "icon": icons["add"], "tooltip": "Add Fog Rectangle", "command": lambda: self._set_fog("add_rect")},
        {"key": "rem_rect", "icon": icons["rem"], "tooltip": "Remove Fog Rectangle", "command": lambda: self._set_fog("rem_rect")},
        {"key": "clear", "icon": icons["clear"], "tooltip": "Clear Fog", "command": self.clear_fog},
        {"key": "reset", "icon": icons["reset"], "tooltip": "Reset Fog", "command": self.reset_fog},
    ]

    fog_dropdown = IconDropdown(fog_section, fog_actions, default_key="add")
    _pack_control(fog_dropdown, trailing=4)
    self._fog_buttons.update(fog_dropdown.option_buttons)
    self._fog_dropdown = fog_dropdown

    shape_label = ctk.CTkLabel(fog_section, text="Fog Shape:") # Clarified label
    _pack_control(shape_label, leading=8, trailing=4)

    self.shape_menu = ctk.CTkOptionMenu(
        fog_section,
        values=["Rectangle", "Circle"],
        command=self._on_brush_shape_change, # This is for fog brush shape
        width=dropdown_width,
    )
    self.shape_menu.set("Rectangle") # Default fog brush shape
    _pack_control(self.shape_menu, trailing=4)

    size_label = ctk.CTkLabel(fog_section, text="Brush Size") # Clarified label
    _pack_control(size_label, leading=4, trailing=4)

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
    _pack_control(self.brush_size_menu, leading=0, trailing=4, pady=6)

    # Key bindings for bracket adjustments (for fog brush)
    self.parent.bind("[", lambda e: self._change_brush(-4))
    self.parent.bind("]", lambda e: self._change_brush(+4))

    # Token controls and fullscreen before the brush size
    token_section = _create_collapsible_section(toolbar, "Tokens")
    token_actions = [
        {"key": "creature", "icon": icons["creat"], "tooltip": "Add Creature", "command": lambda: self.open_entity_picker("Creature")},
        {"key": "npc", "icon": icons["npc"], "tooltip": "Add NPC", "command": lambda: self.open_entity_picker("NPC")},
        {"key": "pc", "icon": icons["pc"], "tooltip": "Add PC", "command": lambda: self.open_entity_picker("PC")},
        {"key": "marker", "icon": icons["marker"], "tooltip": "Add Marker", "command": self.add_marker},
    ]
    token_dropdown = IconDropdown(token_section, token_actions, default_key="npc")
    _pack_control(token_dropdown, trailing=4)

    token_size_label = ctk.CTkLabel(token_section, text="Size") # Renamed label variable
    _pack_control(token_size_label, leading=8, trailing=4)

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
    _pack_control(self.token_size_menu, trailing=4)

    drawing_section = _create_collapsible_section(toolbar, "Drawings")

    drawing_container = ctk.CTkScrollableFrame(
        drawing_section,
        fg_color="transparent",
        orientation="vertical",
    )
    drawing_container.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=(2, 2))

    def _pack_drawing_row(row, *, pady=(4, 2)):
        row.pack(side="top", fill="x", anchor="w", padx=(6, 2), pady=pady)

    drawing_tool_row = ctk.CTkFrame(drawing_container, fg_color="transparent")
    _pack_drawing_row(drawing_tool_row)

    # --- Drawing Tool Selector ---
    tool_label = ctk.CTkLabel(drawing_tool_row, text="Tool")
    _pack_control(tool_label, leading=8, trailing=4)
    drawing_tools = ["Token", "Rectangle", "Oval", "Text", "Whiteboard", "Eraser"]
    self.drawing_tool_menu = ctk.CTkOptionMenu(
        drawing_tool_row,
        values=drawing_tools,
        command=self._on_drawing_tool_change, # To be created in DisplayMapController
        width=dropdown_width,
    )
    # Ensure self.drawing_mode is initialized in DisplayMapController before this
    self.drawing_tool_menu.set(self.drawing_mode.capitalize() if hasattr(self, 'drawing_mode') else "Token")
    _pack_control(self.drawing_tool_menu, trailing=4)

    whiteboard_controls = ctk.CTkFrame(drawing_container, fg_color="transparent")
    _pack_drawing_row(whiteboard_controls)
    self.whiteboard_controls_frame = whiteboard_controls

    self.whiteboard_color_button = ctk.CTkButton(
        whiteboard_controls,
        text="Ink Color",
        width=0,
        command=self._on_pick_whiteboard_color,
    )
    try:
        self.whiteboard_color_button.configure(fg_color=getattr(self, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    _pack_control(self.whiteboard_color_button, leading=0, trailing=4, pady=4)

    width_container = ctk.CTkFrame(whiteboard_controls, fg_color="transparent")
    width_container.pack(side="left", padx=(0, 4), pady=4)
    width_label = ctk.CTkLabel(width_container, text="Width")
    width_label.pack(side="left", padx=(0, 2))
    self.whiteboard_width_slider = ctk.CTkSlider(
        width_container,
        from_=1,
        to=20,
        number_of_steps=19,
        command=self._on_whiteboard_width_change,
        width=110,
    )
    current_width = float(getattr(self, "whiteboard_width", 4))
    self.whiteboard_width_slider.set(current_width)
    width_value_label = ctk.CTkLabel(width_container, text=str(int(current_width)))
    width_value_label.pack(side="left", padx=(4, 0))
    self.whiteboard_width_value_label = width_value_label

    text_controls = ctk.CTkFrame(drawing_container, fg_color="transparent")
    _pack_drawing_row(text_controls)
    self.text_controls_frame = text_controls
    text_size_label = ctk.CTkLabel(text_controls, text="Text Size")
    text_size_label.pack(side="left", padx=(0, 2))
    text_sizes = getattr(self, "text_size_options", [16, 20, 24, 32, 40])
    current_text_size = int(getattr(self, "text_size", text_sizes[0] if text_sizes else 24))
    if current_text_size not in text_sizes:
        text_sizes = sorted(set(list(text_sizes) + [current_text_size]))
    self.text_size_options = list(text_sizes)
    self.text_size_menu = ctk.CTkOptionMenu(
        text_controls,
        values=[str(size) for size in self.text_size_options],
        command=getattr(self, "_on_text_size_change", None) or (lambda _v: None),
        width=dropdown_width,
    )
    self.text_size_menu.set(str(current_text_size))
    self.text_size_menu.pack(side="left", padx=(0, 4), pady=4)

    self.text_color_button = ctk.CTkButton(
        text_controls,
        text="Text Color",
        width=0,
        command=self._on_pick_whiteboard_color,
    )
    try:
        self.text_color_button.configure(fg_color=getattr(self, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    self.text_color_button.pack(side="left", padx=(0, 4), pady=4)

    eraser_controls = ctk.CTkFrame(drawing_container, fg_color="transparent")
    self.eraser_controls_frame = eraser_controls

    eraser_width_container = ctk.CTkFrame(eraser_controls, fg_color="transparent")
    eraser_width_container.pack(side="left", padx=(0, 6), pady=6)
    eraser_width = float(8)
    

    # --- Shape Fill Mode Selector (conditionally visible) ---
    shape_controls_row = ctk.CTkFrame(drawing_container, fg_color="transparent")
    self.shape_controls_row = shape_controls_row

    self.shape_fill_label = ctk.CTkLabel(shape_controls_row, text="Shape Fill:")
    # Packed by _update_shape_controls_visibility
    self.shape_fill_mode_menu = ctk.CTkOptionMenu(
        shape_controls_row,
        values=["Filled", "Border Only"],
        command=self._on_shape_fill_mode_change, # To be created in DisplayMapController
        width=dropdown_width,
    )
    # Ensure self.shape_is_filled is initialized
    self.shape_fill_mode_menu.set("Filled" if hasattr(self, 'shape_is_filled') and self.shape_is_filled else "Border Only")
    # Packed by _update_shape_controls_visibility

    # --- Shape Color Pickers (conditionally visible) ---
    self.shape_fill_color_button = ctk.CTkButton(
        shape_controls_row,
        text="Fill Color",
        width=80,
        command=self._on_pick_shape_fill_color # To be created in DisplayMapController
    )
    # Packed by _update_shape_controls_visibility

    self.shape_border_color_button = ctk.CTkButton(
        shape_controls_row,
        text="Border Color",
        width=100,
        command=self._on_pick_shape_border_color # To be created in DisplayMapController
    )
    # Packed by _update_shape_controls_visibility

    display_section = _create_collapsible_section(toolbar, "Display")
    display_actions = [
        {"key": "save", "icon": icons["save"], "tooltip": "Save Map", "command": self.save_map},
        {
            "key": "rotate_right",
            "icon": icons["rotate"],
            "tooltip": "Rotate Map 90° Right",
            "command": self.rotate_map_background_right,
        },
        {"key": "fullscreen", "icon": icons["fs"], "tooltip": "Fullscreen", "command": self.open_fullscreen},
        {"key": "web", "icon": icons["fs"], "tooltip": "Web Display", "command": self.open_web_display},
        {"key": "chatbot", "icon": icons["chatbot"], "tooltip": "Chatbot", "command": self.open_chatbot_assistant},
    ]
    display_dropdown = IconDropdown(display_section, display_actions, default_key="save")
    _pack_control(display_dropdown, trailing=4)

    hover_font_label = ctk.CTkLabel(display_section, text="Font Size")
    _pack_control(hover_font_label, leading=8, trailing=4)

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
    _pack_control(self.hover_font_size_menu, trailing=4)

    # --- Fit Mode selector ---
    fit_label = ctk.CTkLabel(display_section, text="Fit:")
    _pack_control(fit_label, leading=12, trailing=4)
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
    _pack_control(self.fit_mode_menu, trailing=4)

    plot_twist_section = _create_collapsible_section(toolbar, "Plot Twist")
    plot_twist_container = ctk.CTkFrame(plot_twist_section, fg_color="transparent")
    plot_twist_container.pack(side="left", padx=(6, 6), pady=(6, 6))

    self._plot_twist_result_var = ctk.StringVar(value="No plot twist rolled yet.")

    plot_twist_title = ctk.CTkLabel(
        plot_twist_container,
        text="Latest:",
        font=("Segoe UI", 12, "bold"),
    )
    plot_twist_title.pack(anchor="w")

    plot_twist_result_label = ctk.CTkLabel(
        plot_twist_container,
        textvariable=self._plot_twist_result_var,
        justify="left",
        wraplength=260,
    )
    plot_twist_result_label.pack(anchor="w", pady=(2, 4))

    def _render_plot_twist(result):
        if not result:
            self._plot_twist_result_var.set("No plot twist rolled yet.")
            return
        message = result.result or "No plot twist rolled yet."
        if len(message) > 80:
            message = f"{message[:77].rstrip()}..."
        self._plot_twist_result_var.set(message)

    def _roll_plot_twist():
        _render_plot_twist(roll_plot_twist())

    plot_twist_actions = ctk.CTkFrame(plot_twist_container, fg_color="transparent")
    plot_twist_actions.pack(anchor="w", pady=(2, 0))
    plot_twist_roll_button = ctk.CTkButton(
        plot_twist_actions,
        text="Roll",
        width=70,
        command=_roll_plot_twist,
    )
    plot_twist_roll_button.pack(side="left", padx=(0, 6))

    def _on_plot_twist_update(result):
        _render_plot_twist(result)

    add_plot_twist_listener(_on_plot_twist_update)
    self._plot_twist_toolbar_listener = _on_plot_twist_update
    _render_plot_twist(get_latest_plot_twist())

    def _on_toolbar_destroy(event):
        if event.widget is not self.parent:
            return
        listener = getattr(self, "_plot_twist_toolbar_listener", None)
        if listener:
            remove_plot_twist_listener(listener)
            self._plot_twist_toolbar_listener = None

    self.parent.bind("<Destroy>", _on_toolbar_destroy, add="+")

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

    dropdown = getattr(self, "_fog_dropdown", None)
    if dropdown:
        dropdown.set_active(active_mode, active_style=active_style, default_style=default_style)

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
