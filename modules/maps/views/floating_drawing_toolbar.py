"""Floating drawing and fog palette for map canvas."""

import tkinter as tk
import customtkinter as ctk

from modules.helpers.logging_helper import log_module_import
from modules.ui.icon_dropdown import IconDropdown
from modules.maps.marker_types import MARKER_TYPE_FILTER_LABELS
from modules.maps.views.floating_toolbar.layout import (
    BORDER,
    DROPDOWN_WIDTH,
    PALETTE_BG,
    SLIDER_WIDTH,
    TEXT_MUTED,
    add_stacked_control,
    create_row,
    create_section,
)

log_module_import(__name__)

def _build_floating_drawing_toolbar(self):
    """Build a compact floating palette for fog and drawing controls."""
    host = getattr(self, "parent", None)
    canvas = getattr(self, "canvas", None)
    if host is None or canvas is None:
        return None

    existing = getattr(self, "floating_drawing_toolbar", None)
    if existing is not None:
        try:
            existing.destroy()
        except tk.TclError:
            pass

    dropdown_width = DROPDOWN_WIDTH
    slider_width = SLIDER_WIDTH
    palette = ctk.CTkFrame(
        host,
        fg_color=PALETTE_BG,
        border_width=1,
        border_color=BORDER,
        corner_radius=12,
    )
    self.floating_drawing_toolbar = palette

    header = ctk.CTkFrame(palette, fg_color="#242424", corner_radius=10)
    header.pack(side="top", fill="x", padx=4, pady=(4, 2))
    handle = ctk.CTkLabel(header, text="☰", text_color=TEXT_MUTED, cursor="fleur")
    handle.pack(side="left", padx=(6, 4), pady=3)

    content = ctk.CTkFrame(palette, fg_color="transparent")
    content.pack(side="top", fill="both", expand=True, padx=4, pady=(0, 4))
    self.floating_drawing_toolbar_content = content

    collapsed = tk.BooleanVar(value=False)

    def _toggle_palette():
        if collapsed.get():
            content.pack(side="top", fill="both", expand=True, padx=4, pady=(0, 4))
            collapse_button.configure(text="−")
            collapsed.set(False)
        else:
            content.pack_forget()
            collapse_button.configure(text="+")
            collapsed.set(True)
        try:
            palette.lift()
        except tk.TclError:
            pass

    collapse_button = ctk.CTkButton(header, text="−", width=24, height=22, command=_toggle_palette)
    collapse_button.pack(side="right", padx=(1, 4), pady=3)

    drag_state = {"x": 0, "y": 0}

    def _drag_start(event):
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root
        try:
            palette.lift()
        except tk.TclError:
            pass

    def _drag_motion(event):
        try:
            info = palette.place_info()
            current_x = int(float(info.get("x", 0)))
            current_y = int(float(info.get("y", 0)))
        except (tk.TclError, TypeError, ValueError):
            return
        dx = event.x_root - drag_state["x"]
        dy = event.y_root - drag_state["y"]
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root
        palette.place_configure(relx=0, x=max(8, current_x + dx), y=max(8, current_y + dy), anchor="nw")

    for draggable in (header, handle):
        draggable.bind("<ButtonPress-1>", _drag_start)
        draggable.bind("<B1-Motion>", _drag_motion)

    def _section(title):
        return create_section(content, title)

    def _row(parent):
        return create_row(parent)

    def _stacked_control(parent, label, widget, *, pady=(0, 4)):
        return add_stacked_control(parent, label, widget, pady=pady)

    icons = {
        "add": self.load_icon("assets/icons/brush.png", (24, 24)),
        "rem": self.load_icon("assets/icons/eraser.png", (24, 24)),
        "clear": self.load_icon("assets/icons/empty.png", (24, 24)),
        "reset": self.load_icon("assets/icons/full.png", (24, 24)),
        "npc": self.load_icon("assets/icons/npc.png", (24, 24)),
        "creat": self.load_icon("assets/icons/creature.png", (24, 24)),
        "pc": self.load_icon("assets/icons/pc.png", (24, 24)),
        "marker": self.load_icon("assets/icons/marker.png", (24, 24)),
    }

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

    fog_body = _section("Fog")
    fog_actions = [
        {"key": "add", "icon": icons["add"], "tooltip": "Add Fog", "command": lambda: self._set_fog("add")},
        {"key": "rem", "icon": icons["rem"], "tooltip": "Remove Fog", "command": lambda: self._set_fog("rem")},
        {"key": "add_rect", "icon": icons["add"], "tooltip": "Add Fog Rectangle", "command": lambda: self._set_fog("add_rect")},
        {"key": "rem_rect", "icon": icons["rem"], "tooltip": "Remove Fog Rectangle", "command": lambda: self._set_fog("rem_rect")},
        {"key": "clear", "icon": icons["clear"], "tooltip": "Clear Fog", "command": self.clear_fog},
        {"key": "reset", "icon": icons["reset"], "tooltip": "Reset Fog", "command": self.reset_fog},
    ]
    fog_row = _row(fog_body)
    fog_dropdown = IconDropdown(fog_row, fog_actions, default_key="add", button_size=(24, 24))
    fog_dropdown.pack(side="top", anchor="w", padx=0, pady=3)
    self._fog_buttons.update(fog_dropdown.option_buttons)
    self._fog_dropdown = fog_dropdown

    self.shape_menu = ctk.CTkOptionMenu(
        fog_body,
        values=["Rectangle", "Circle"],
        command=self._on_brush_shape_change,
        width=dropdown_width,
    )
    self.shape_menu.set("Rectangle")
    _stacked_control(fog_body, "Shape", self.shape_menu)

    brush_size_options = list(getattr(self, "brush_size_options", list(range(4, 129, 4))))
    current_brush_size = int(getattr(self, "brush_size", brush_size_options[0] if brush_size_options else 32))
    if current_brush_size not in brush_size_options:
        brush_size_options.append(current_brush_size)
        brush_size_options = sorted(set(brush_size_options))
    self.brush_size_options = list(brush_size_options)
    self.brush_size_menu = ctk.CTkOptionMenu(
        fog_body,
        values=[str(size) for size in self.brush_size_options],
        command=self._on_brush_size_change,
        width=dropdown_width,
    )
    self.brush_size_menu.set(str(current_brush_size))
    _stacked_control(fog_body, "Size", self.brush_size_menu)

    tools_body = _section("Tools")
    drawing_tools = ["Token", "Rectangle", "Oval", "Text", "Whiteboard", "Eraser"]
    self.drawing_tool_menu = ctk.CTkOptionMenu(
        tools_body,
        values=drawing_tools,
        command=self._on_drawing_tool_change,
        width=dropdown_width,
    )
    current_tool = self.drawing_mode.capitalize() if hasattr(self, "drawing_mode") else "Token"
    self.drawing_tool_menu.set(current_tool if current_tool in drawing_tools else "Token")
    _stacked_control(tools_body, "Tool", self.drawing_tool_menu)

    whiteboard_controls = ctk.CTkFrame(tools_body, fg_color="transparent")
    self.whiteboard_controls_frame = whiteboard_controls

    self.whiteboard_color_button = ctk.CTkButton(
        whiteboard_controls,
        text="Ink Color",
        width=dropdown_width,
        command=self._on_pick_whiteboard_color,
    )
    try:
        self.whiteboard_color_button.configure(fg_color=getattr(self, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    self.whiteboard_color_button.pack(side="top", fill="x", padx=0, pady=(0, 4))

    width_container = ctk.CTkFrame(whiteboard_controls, fg_color="transparent")
    width_container.pack(side="top", fill="x", padx=0, pady=(0, 4))
    ctk.CTkLabel(width_container, text="Width", text_color=TEXT_MUTED).pack(side="top", anchor="w", padx=0, pady=(0, 2))
    self.whiteboard_width_slider = ctk.CTkSlider(
        width_container,
        from_=1,
        to=20,
        number_of_steps=19,
        command=self._on_whiteboard_width_change,
        width=slider_width,
    )
    current_width = float(getattr(self, "whiteboard_width", 4))
    self.whiteboard_width_slider.set(current_width)
    self.whiteboard_width_slider.pack(side="top", fill="x", padx=0)
    self.whiteboard_width_value_label = ctk.CTkLabel(width_container, text=str(int(current_width)), text_color=TEXT_MUTED)
    self.whiteboard_width_value_label.pack(side="top", anchor="e", padx=0)

    text_controls = ctk.CTkFrame(tools_body, fg_color="transparent")
    self.text_controls_frame = text_controls
    ctk.CTkLabel(text_controls, text="Text Size", text_color=TEXT_MUTED).pack(side="top", anchor="w", padx=0, pady=(0, 2))
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
    self.text_size_menu.pack(side="top", fill="x", padx=0, pady=(0, 4))

    self.text_color_button = ctk.CTkButton(
        text_controls,
        text="Text Color",
        width=dropdown_width,
        command=self._on_pick_whiteboard_color,
    )
    try:
        self.text_color_button.configure(fg_color=getattr(self, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    self.text_color_button.pack(side="top", fill="x", padx=0, pady=(0, 4))

    eraser_controls = ctk.CTkFrame(tools_body, fg_color="transparent")
    self.eraser_controls_frame = eraser_controls
    eraser_width_container = ctk.CTkFrame(eraser_controls, fg_color="transparent")
    eraser_width_container.pack(side="top", fill="x", padx=0, pady=(0, 4))
    ctk.CTkLabel(eraser_width_container, text="Radius", text_color=TEXT_MUTED).pack(side="top", anchor="w", padx=0, pady=(0, 2))
    self.whiteboard_eraser_slider = ctk.CTkSlider(
        eraser_width_container,
        from_=2,
        to=40,
        number_of_steps=38,
        command=getattr(self, "_on_eraser_radius_change", None) or (lambda _v: None),
        width=slider_width,
    )
    current_eraser_radius = float(getattr(self, "whiteboard_eraser_radius", 8))
    self.whiteboard_eraser_slider.set(current_eraser_radius)
    self.whiteboard_eraser_slider.pack(side="top", fill="x", padx=0)
    self.eraser_radius_value_label = ctk.CTkLabel(
        eraser_width_container,
        text=str(int(round(current_eraser_radius))),
        text_color=TEXT_MUTED,
    )
    self.eraser_radius_value_label.pack(side="top", anchor="e", padx=0)

    tokens_body = _section("Tokens")
    token_actions = [
        {"key": "creature", "icon": icons["creat"], "tooltip": "Add Creature", "command": lambda: self.open_entity_picker("Creature")},
        {"key": "npc", "icon": icons["npc"], "tooltip": "Add NPC", "command": lambda: self.open_entity_picker("NPC")},
        {"key": "pc", "icon": icons["pc"], "tooltip": "Add PC", "command": lambda: self.open_entity_picker("PC")},
        {"key": "marker", "icon": icons["marker"], "tooltip": "Add Marker", "command": self.add_marker},
    ]
    token_dropdown = IconDropdown(tokens_body, token_actions, default_key="npc", button_size=(24, 24))
    token_dropdown.pack(side="top", anchor="w", padx=0, pady=3)

    token_size_options = list(getattr(self, "token_size_options", list(range(16, 129, 8))))
    current_token_size = int(getattr(self, "token_size", token_size_options[0] if token_size_options else 48))
    if current_token_size not in token_size_options:
        token_size_options.append(current_token_size)
        token_size_options = sorted(set(token_size_options))
    self.token_size_options = list(token_size_options)
    self.token_size_menu = ctk.CTkOptionMenu(
        tokens_body,
        values=[str(size) for size in self.token_size_options],
        command=self._on_token_size_change,
        width=dropdown_width,
    )
    self.token_size_menu.set(str(current_token_size))
    _stacked_control(tokens_body, "Size", self.token_size_menu)

    self.marker_type_filter_menu = ctk.CTkOptionMenu(
        tokens_body,
        values=MARKER_TYPE_FILTER_LABELS,
        command=getattr(self, "_on_marker_type_filter_change", None) or (lambda _v: None),
        width=dropdown_width,
    )
    self.marker_type_filter_menu.set(getattr(self, "marker_type_filter", "All Types") or "All Types")
    _stacked_control(tokens_body, "Marker Type", self.marker_type_filter_menu)

    shape_controls_row = ctk.CTkFrame(tools_body, fg_color="transparent")
    self.shape_controls_row = shape_controls_row
    self.shape_fill_label = ctk.CTkLabel(shape_controls_row, text="Shape Fill", text_color=TEXT_MUTED)
    self.shape_fill_mode_menu = ctk.CTkOptionMenu(
        shape_controls_row,
        values=["Filled", "Border Only"],
        command=self._on_shape_fill_mode_change,
        width=dropdown_width,
    )
    self.shape_fill_mode_menu.set("Filled" if hasattr(self, "shape_is_filled") and self.shape_is_filled else "Border Only")
    self.shape_fill_color_button = ctk.CTkButton(
        shape_controls_row,
        text="Fill Color",
        width=dropdown_width,
        command=self._on_pick_shape_fill_color,
    )
    self.shape_border_color_button = ctk.CTkButton(
        shape_controls_row,
        text="Border Color",
        width=dropdown_width,
        command=self._on_pick_shape_border_color,
    )

    try:
        toolbar_height = int(getattr(self, "_toolbar_container", host).winfo_height())
    except Exception:
        toolbar_height = 0
    if toolbar_height <= 1:
        toolbar_height = 72
    palette.place(relx=0.5, y=toolbar_height + 12, anchor="n")
    try:
        palette.lift()
    except tk.TclError:
        pass

    if hasattr(self, "_update_shape_controls_visibility"):
        self._update_shape_controls_visibility()
    if hasattr(self, "_update_fog_button_states"):
        self._update_fog_button_states()

    return palette
