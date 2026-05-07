"""View for map toolbar."""

import tkinter as tk
import customtkinter as ctk
from modules.ui.icon_dropdown import IconDropdown
from modules.helpers.logging_helper import log_module_import
from modules.scenarios.plot_twist_panel import PlotTwistPanel
from modules.maps.measurement.templates import MEASUREMENT_TEMPLATE_LABELS
from modules.maps.marker_types import MARKER_TYPE_FILTER_LABELS

log_module_import(__name__)

def _build_toolbar(self):
    """Build toolbar."""
    section_tracker = {"count": 0}
    horizontal_spacing = 4
    control_pady = 4

    def _pack_control(widget, *, leading=0, trailing=None, pady=None):
        """Pack control."""
        padx = (leading, horizontal_spacing if trailing is None else trailing)
        widget.pack(side="left", padx=padx, pady=control_pady if pady is None else pady)

    def _create_collapsible_section(parent, title):
        """Create collapsible section."""
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
            """Toggle the operation."""
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
        "save":  self.load_icon("assets/icons/save.png",     (48,48)),
        "fs":    self.load_icon("assets/icons/expand.png",   (48,48)),
        "rotate":    self.load_icon("assets/icons/turn_background_icon.png",   (48,48)),
        "chatbot":    self.load_icon("assets/icons/chatbot.png",       (48,48)),

    }

    dropdown_width = 0

    # Fog and drawing controls are hosted by the floating canvas palette.

    # Key bindings for bracket adjustments (for fog brush)
    self.parent.bind("[", lambda e: self._change_brush(-4))
    self.parent.bind("]", lambda e: self._change_brush(+4))

    # Token creation controls live in the one-column floating drawing palette.
    # Marker filtering belongs to the persistent top toolbar so it stays visible.

    token_section = _create_collapsible_section(toolbar, "Tokens")
    ctk.CTkLabel(token_section, text="Marker Type").pack(side="left", padx=(8, 4), pady=6)
    self.marker_type_filter_menu = ctk.CTkOptionMenu(
        token_section,
        values=MARKER_TYPE_FILTER_LABELS,
        command=getattr(self, "_on_marker_type_filter_change", None) or (lambda _v: None),
        width=110,
    )
    self.marker_type_filter_menu.set(getattr(self, "marker_type_filter", "All Types") or "All Types")
    _pack_control(self.marker_type_filter_menu, trailing=6, pady=6)

    measure_section = _create_collapsible_section(toolbar, "Meas.")
    ctk.CTkLabel(measure_section, text="Template").pack(side="left", padx=(8, 4), pady=6)
    self.measure_template_menu = ctk.CTkOptionMenu(
        measure_section,
        values=MEASUREMENT_TEMPLATE_LABELS,
        command=getattr(self, "_on_measure_template_change", None) or (lambda _v: None),
        width=110,
    )
    self.measure_template_menu.set(getattr(self, "measure_template_label", "Line"))
    _pack_control(self.measure_template_menu, trailing=4, pady=6)

    self.measure_button = ctk.CTkButton(
        measure_section,
        text="Meas.",
        width=100,
        command=getattr(self, "_toggle_measure_mode", None) or (lambda: None),
    )
    _pack_control(self.measure_button, trailing=4)

    ctk.CTkLabel(measure_section, text="Cell px").pack(side="left", padx=(8, 4), pady=6)
    self.measure_cell_entry = ctk.CTkEntry(measure_section, width=62)
    self.measure_cell_entry.insert(0, str(int(getattr(self, "measure_grid_cell_pixels", 50))))
    _pack_control(self.measure_cell_entry, trailing=4, pady=6)

    ctk.CTkLabel(measure_section, text="Scale").pack(side="left", padx=(4, 4), pady=6)
    self.measure_scale_entry = ctk.CTkEntry(measure_section, width=62)
    self.measure_scale_entry.insert(0, str(int(getattr(self, "measure_grid_scale", 5))))
    _pack_control(self.measure_scale_entry, trailing=2, pady=6)
    self.measure_unit_label = ctk.CTkLabel(measure_section, text=getattr(self, "measure_unit", "m") + "/cell")
    _pack_control(self.measure_unit_label, trailing=6, pady=6)

    self.clear_measurements_button = ctk.CTkButton(
        measure_section,
        text="Clear",
        width=80,
        command=getattr(self, "clear_measurements", None) or (lambda: None),
    )
    _pack_control(self.clear_measurements_button, trailing=6)

    # Drawing-specific controls live in the floating drawing palette.

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
    plot_twist_panel = PlotTwistPanel(
        plot_twist_section,
        compact=True,
        show_title=False,
        layout="toolbar",
        fg_color="transparent",
    )
    plot_twist_panel.pack(side="left", padx=(6, 6), pady=(6, 6))

    # Initial visibility update for shape controls (call method on self)
    if hasattr(self, '_update_shape_controls_visibility'):
        self._update_shape_controls_visibility()

    self._update_fog_button_states()

def _on_brush_size_change(self, val): # This is for FOG brush
    """Handle brush size change."""
    try:
        size = int(val)
    except (TypeError, ValueError):
        return
    self.brush_size = size
    options = list(getattr(self, "brush_size_options", []))
    if size not in options:
        # Handle the branch where size is not in options.
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
    """Handle brush shape change."""
    # normalize to lowercase for comparisons; the compact floating toolbar labels
    # the circular brush as Oval to match the drawing tool wording.
    self.brush_shape = "circle" if str(val).lower() == "oval" else str(val).lower()

def _change_brush(self, delta): # This is for FOG brush
    """Internal helper for change brush."""
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
    """Handle token size change."""
    try:
        size = int(val)
    except (TypeError, ValueError):
        return
    self.token_size = size
    options = list(getattr(self, "token_size_options", []))
    if size not in options:
        # Handle the branch where size is not in options.
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
        # Process each (mode, button) from buttons.items().
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
