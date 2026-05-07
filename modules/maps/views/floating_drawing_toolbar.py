"""Floating drawing and fog palettes for map canvases."""

import tkinter as tk
import customtkinter as ctk

from modules.helpers.logging_helper import log_module_import
from modules.maps.marker_types import MARKER_TYPE_FILTER_LABELS
from modules.maps.measurement.templates import MEASUREMENT_TEMPLATE_LABELS
from modules.maps.utils.icon_loader import load_icon
from modules.maps.views.floating_toolbar.layout import (
    BORDER,
    PALETTE_BG,
    SLIDER_WIDTH,
    TEXT_MUTED,
    add_stacked_control,
    create_row,
    create_section,
)
from modules.maps.views.floating_toolbar.shape_selector import add_shape_icon_selector
from modules.maps.views.floating_toolbar.slim_option_menu import create_slim_option_menu
from modules.ui.icon_dropdown import IconDropdown

log_module_import(__name__)


def _destroy_existing_palette(owner):
    """Destroy the currently attached floating palette, if any."""
    existing = getattr(owner, "floating_drawing_toolbar", None)
    if existing is not None:
        try:
            existing.destroy()
        except tk.TclError:
            pass


def _create_floating_palette(owner, host, *, x=8, y=84, title="☰"):
    """Create a draggable floating palette attached to *host*."""
    _destroy_existing_palette(owner)

    palette = ctk.CTkFrame(
        host,
        fg_color=PALETTE_BG,
        border_width=1,
        border_color=BORDER,
        corner_radius=12,
    )
    owner.floating_drawing_toolbar = palette

    header = ctk.CTkFrame(palette, fg_color="#242424", corner_radius=10)
    header.pack(side="top", fill="x", padx=4, pady=(4, 2))
    handle = ctk.CTkLabel(header, text=title, text_color=TEXT_MUTED, cursor="fleur")
    handle.pack(side="left", padx=(6, 4), pady=3)

    content = ctk.CTkFrame(palette, fg_color="transparent")
    content.pack(side="top", fill="both", expand=True, padx=4, pady=(0, 4))
    owner.floating_drawing_toolbar_content = content

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

    palette.place(relx=0, x=x, y=y, anchor="nw")
    try:
        palette.lift()
    except tk.TclError:
        pass

    return palette, content


def _load_icon(owner, path, size):
    """Load an icon for either the MapTool controller or the WorldMap panel."""
    loader = getattr(owner, "load_icon", None)
    if callable(loader):
        return loader(path, size)
    return load_icon(owner, path, size)


def _build_fog_controls(owner, parent, icons, *, include_global_actions):
    """Add fog brush controls to the floating palette."""
    owner._fog_button_default_style = {
        "fg_color": "#0077CC",
        "hover_color": "#005fa3",
        "border_color": "#005fa3",
        "border_width": 1,
    }
    owner._fog_button_active_style = {
        "fg_color": "#004c80",
        "hover_color": "#004c80",
        "border_color": "#d7263d",
        "border_width": 3,
    }
    owner._fog_buttons = {}

    fog_body = create_section(parent, "Fog")
    fog_actions = [
        {"key": "add", "icon": icons["add"], "tooltip": "Add Fog", "command": lambda: owner._set_fog("add")},
        {"key": "rem", "icon": icons["rem"], "tooltip": "Remove Fog", "command": lambda: owner._set_fog("rem")},
        {"key": "add_rect", "icon": icons["add"], "tooltip": "Add Fog Rectangle", "command": lambda: owner._set_fog("add_rect")},
        {"key": "rem_rect", "icon": icons["rem"], "tooltip": "Remove Fog Rectangle", "command": lambda: owner._set_fog("rem_rect")},
    ]
    if include_global_actions:
        fog_actions.extend(
            [
                {"key": "clear", "icon": icons["clear"], "tooltip": "Clear Fog", "command": owner.clear_fog},
                {"key": "reset", "icon": icons["reset"], "tooltip": "Reset Fog", "command": owner.reset_fog},
            ]
        )

    fog_row = create_row(fog_body)
    fog_dropdown = IconDropdown(fog_row, fog_actions, default_key="add", button_size=(24, 24), show_arrow=False)
    fog_dropdown.pack(side="top", anchor="center", padx=0, pady=3)
    owner._fog_buttons.update(fog_dropdown.option_buttons)
    owner._fog_dropdown = fog_dropdown

    owner.shape_menu = add_shape_icon_selector(fog_body, owner._on_brush_shape_change)

    brush_size_options = list(getattr(owner, "brush_size_options", list(range(4, 129, 4))))
    current_brush_size = int(getattr(owner, "brush_size", brush_size_options[0] if brush_size_options else 32))
    if current_brush_size not in brush_size_options:
        brush_size_options.append(current_brush_size)
        brush_size_options = sorted(set(brush_size_options))
    owner.brush_size_options = list(brush_size_options)
    owner.brush_size_menu = create_slim_option_menu(
        fog_body,
        values=[str(size) for size in owner.brush_size_options],
        command=owner._on_brush_size_change,
    )
    owner.brush_size_menu.set(str(current_brush_size))
    add_stacked_control(fog_body, "Size", owner.brush_size_menu)


def _build_measurement_controls(panel, parent):
    """Add WorldMap measurement controls to the floating palette."""
    measure_body = create_section(parent, "Measure")
    panel.measure_template_menu = create_slim_option_menu(
        measure_body,
        values=MEASUREMENT_TEMPLATE_LABELS,
        command=getattr(panel, "_on_measure_template_change", None) or (lambda _v: None),
    )
    panel.measure_template_menu.set(getattr(panel, "measure_template_label", "Line"))
    add_stacked_control(measure_body, "Template", panel.measure_template_menu)

    panel.measure_button = ctk.CTkButton(
        measure_body,
        text="Measure",
        width=76,
        command=getattr(panel, "_toggle_measure_mode", None) or (lambda: None),
    )
    panel.measure_button.pack(side="top", anchor="center", padx=0, pady=(0, 4))

    panel.measure_cell_entry = ctk.CTkEntry(measure_body, width=76, justify="center")
    panel.measure_cell_entry.insert(0, str(int(getattr(panel, "measure_grid_cell_pixels", 50))))
    add_stacked_control(measure_body, "Cell px", panel.measure_cell_entry)

    panel.measure_scale_entry = ctk.CTkEntry(measure_body, width=76, justify="center")
    panel.measure_scale_entry.insert(0, str(int(getattr(panel, "measure_grid_scale", 5))))
    add_stacked_control(measure_body, "Scale", panel.measure_scale_entry)

    panel.measure_unit_label = ctk.CTkLabel(measure_body, text=getattr(panel, "measure_unit", "m") + "/cell", text_color=TEXT_MUTED)
    panel.measure_unit_label.pack(side="top", anchor="center", padx=0, pady=(0, 4))

    panel.clear_measurements_button = ctk.CTkButton(
        measure_body,
        text="Clear",
        width=76,
        command=getattr(panel, "clear_measurements", None) or (lambda: None),
    )
    panel.clear_measurements_button.pack(side="top", anchor="center", padx=0, pady=(0, 4))


def build_maptool_floating_drawing_toolbar(controller):
    """Build the map-tool floating drawing palette."""
    host = getattr(controller, "parent", None)
    canvas = getattr(controller, "canvas", None)
    if host is None or canvas is None:
        return None

    try:
        toolbar_height = int(getattr(controller, "_toolbar_container", host).winfo_height())
    except Exception:
        toolbar_height = 0
    if toolbar_height <= 1:
        toolbar_height = 72

    palette, content = _create_floating_palette(controller, host, y=toolbar_height + 12)
    slider_width = SLIDER_WIDTH

    icons = {
        "add": _load_icon(controller, "assets/icons/brush.png", (24, 24)),
        "rem": _load_icon(controller, "assets/icons/eraser.png", (24, 24)),
        "clear": _load_icon(controller, "assets/icons/empty.png", (24, 24)),
        "reset": _load_icon(controller, "assets/icons/full.png", (24, 24)),
        "npc": _load_icon(controller, "assets/icons/npc.png", (24, 24)),
        "creat": _load_icon(controller, "assets/icons/creature.png", (24, 24)),
        "pc": _load_icon(controller, "assets/icons/pc.png", (24, 24)),
        "marker": _load_icon(controller, "assets/icons/marker.png", (24, 24)),
    }

    _build_fog_controls(controller, content, icons, include_global_actions=True)

    tools_body = create_section(content, "Tools")
    drawing_tools = ["Token", "Rectangle", "Oval", "Text", "Whiteboard", "Eraser"]
    controller.drawing_tool_menu = create_slim_option_menu(
        tools_body,
        values=drawing_tools,
        command=controller._on_drawing_tool_change,
    )
    current_tool = controller.drawing_mode.capitalize() if hasattr(controller, "drawing_mode") else "Token"
    controller.drawing_tool_menu.set(current_tool if current_tool in drawing_tools else "Token")
    add_stacked_control(tools_body, "Tool", controller.drawing_tool_menu)

    whiteboard_controls = ctk.CTkFrame(tools_body, fg_color="transparent")
    controller.whiteboard_controls_frame = whiteboard_controls

    controller.whiteboard_color_button = ctk.CTkButton(
        whiteboard_controls,
        text="Ink Color",
        width=70,
        command=controller._on_pick_whiteboard_color,
    )
    try:
        controller.whiteboard_color_button.configure(fg_color=getattr(controller, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    controller.whiteboard_color_button.pack(side="top", anchor="center", padx=0, pady=(0, 4))

    width_container = ctk.CTkFrame(whiteboard_controls, fg_color="transparent")
    width_container.pack(side="top", fill="x", padx=0, pady=(0, 4))
    ctk.CTkLabel(width_container, text="Width", text_color=TEXT_MUTED).pack(side="top", fill="x", padx=0, pady=(0, 2))
    controller.whiteboard_width_slider = ctk.CTkSlider(
        width_container,
        from_=1,
        to=20,
        number_of_steps=19,
        command=controller._on_whiteboard_width_change,
        width=slider_width,
    )
    current_width = float(getattr(controller, "whiteboard_width", 4))
    controller.whiteboard_width_slider.set(current_width)
    controller.whiteboard_width_slider.pack(side="top", fill="x", padx=0)
    controller.whiteboard_width_value_label = ctk.CTkLabel(width_container, text=str(int(current_width)), text_color=TEXT_MUTED)
    controller.whiteboard_width_value_label.pack(side="top", fill="x", padx=0)

    text_controls = ctk.CTkFrame(tools_body, fg_color="transparent")
    controller.text_controls_frame = text_controls
    ctk.CTkLabel(text_controls, text="Text Size", text_color=TEXT_MUTED).pack(side="top", fill="x", padx=0, pady=(0, 2))
    text_sizes = getattr(controller, "text_size_options", [16, 20, 24, 32, 40])
    current_text_size = int(getattr(controller, "text_size", text_sizes[0] if text_sizes else 24))
    if current_text_size not in text_sizes:
        text_sizes = sorted(set(list(text_sizes) + [current_text_size]))
    controller.text_size_options = list(text_sizes)
    controller.text_size_menu = create_slim_option_menu(
        text_controls,
        values=[str(size) for size in controller.text_size_options],
        command=getattr(controller, "_on_text_size_change", None) or (lambda _v: None),
    )
    controller.text_size_menu.set(str(current_text_size))
    controller.text_size_menu.pack(side="top", anchor="center", padx=0, pady=(0, 4))

    controller.text_color_button = ctk.CTkButton(
        text_controls,
        text="Text Color",
        width=76,
        command=controller._on_pick_whiteboard_color,
    )
    try:
        controller.text_color_button.configure(fg_color=getattr(controller, "whiteboard_color", "#FF0000"))
    except tk.TclError:
        pass
    controller.text_color_button.pack(side="top", anchor="center", padx=0, pady=(0, 4))

    eraser_controls = ctk.CTkFrame(tools_body, fg_color="transparent")
    controller.eraser_controls_frame = eraser_controls
    eraser_width_container = ctk.CTkFrame(eraser_controls, fg_color="transparent")
    eraser_width_container.pack(side="top", fill="x", padx=0, pady=(0, 4))
    ctk.CTkLabel(eraser_width_container, text="Radius", text_color=TEXT_MUTED).pack(side="top", fill="x", padx=0, pady=(0, 2))
    controller.whiteboard_eraser_slider = ctk.CTkSlider(
        eraser_width_container,
        from_=2,
        to=40,
        number_of_steps=38,
        command=getattr(controller, "_on_eraser_radius_change", None) or (lambda _v: None),
        width=slider_width,
    )
    current_eraser_radius = float(getattr(controller, "whiteboard_eraser_radius", 8))
    controller.whiteboard_eraser_slider.set(current_eraser_radius)
    controller.whiteboard_eraser_slider.pack(side="top", fill="x", padx=0)
    controller.eraser_radius_value_label = ctk.CTkLabel(
        eraser_width_container,
        text=str(int(round(current_eraser_radius))),
        text_color=TEXT_MUTED,
    )
    controller.eraser_radius_value_label.pack(side="top", fill="x", padx=0)

    tokens_body = create_section(content, "Tokens")
    token_actions = [
        {"key": "creature", "icon": icons["creat"], "tooltip": "Add Creature", "command": lambda: controller.open_entity_picker("Creature")},
        {"key": "npc", "icon": icons["npc"], "tooltip": "Add NPC", "command": lambda: controller.open_entity_picker("NPC")},
        {"key": "pc", "icon": icons["pc"], "tooltip": "Add PC", "command": lambda: controller.open_entity_picker("PC")},
        {"key": "marker", "icon": icons["marker"], "tooltip": "Add Marker", "command": controller.add_marker},
    ]
    token_dropdown = IconDropdown(tokens_body, token_actions, default_key="npc", button_size=(24, 24), show_arrow=False)
    token_dropdown.pack(side="top", anchor="center", padx=0, pady=3)

    token_size_options = list(getattr(controller, "token_size_options", list(range(16, 129, 8))))
    current_token_size = int(getattr(controller, "token_size", token_size_options[0] if token_size_options else 48))
    if current_token_size not in token_size_options:
        token_size_options.append(current_token_size)
        token_size_options = sorted(set(token_size_options))
    controller.token_size_options = list(token_size_options)
    controller.token_size_menu = create_slim_option_menu(
        tokens_body,
        values=[str(size) for size in controller.token_size_options],
        command=controller._on_token_size_change,
    )
    controller.token_size_menu.set(str(current_token_size))
    add_stacked_control(tokens_body, "Size", controller.token_size_menu)

    shape_controls_row = ctk.CTkFrame(tools_body, fg_color="transparent")
    controller.shape_controls_row = shape_controls_row
    controller.shape_fill_label = ctk.CTkLabel(shape_controls_row, text="Shape Fill", text_color=TEXT_MUTED)
    controller.shape_fill_mode_menu = create_slim_option_menu(
        shape_controls_row,
        values=["Filled", "Border Only"],
        command=controller._on_shape_fill_mode_change,
    )
    controller.shape_fill_mode_menu.set("Filled" if hasattr(controller, "shape_is_filled") and controller.shape_is_filled else "Border Only")
    controller.shape_fill_color_button = ctk.CTkButton(
        shape_controls_row,
        text="Fill Color",
        width=70,
        command=controller._on_pick_shape_fill_color,
    )
    controller.shape_border_color_button = ctk.CTkButton(
        shape_controls_row,
        text="Border Color",
        width=88,
        command=controller._on_pick_shape_border_color,
    )

    if hasattr(controller, "_update_shape_controls_visibility"):
        controller._update_shape_controls_visibility()
    if hasattr(controller, "_update_fog_button_states"):
        controller._update_fog_button_states()

    return palette


def build_world_map_floating_tools(panel):
    """Build the WorldMap floating tools attached to the canvas surface."""
    host = getattr(panel, "canvas_container", None)
    canvas = getattr(panel, "canvas", None)
    if host is None or canvas is None:
        return None

    palette, content = _create_floating_palette(panel, host, x=20, y=20)
    icons = {
        "add": _load_icon(panel, "assets/icons/brush.png", (24, 24)),
        "rem": _load_icon(panel, "assets/icons/eraser.png", (24, 24)),
        "clear": _load_icon(panel, "assets/icons/empty.png", (24, 24)),
        "reset": _load_icon(panel, "assets/icons/full.png", (24, 24)),
        "npc": _load_icon(panel, "assets/icons/npc.png", (24, 24)),
        "creat": _load_icon(panel, "assets/icons/creature.png", (24, 24)),
        "pc": _load_icon(panel, "assets/icons/pc.png", (24, 24)),
        "marker": _load_icon(panel, "assets/icons/marker.png", (24, 24)),
    }

    _build_fog_controls(panel, content, icons, include_global_actions=False)
    _build_measurement_controls(panel, content)

    entities_body = create_section(content, "Entities")
    entity_actions = [
        {"key": "npc", "icon": icons["npc"], "tooltip": "Add NPC", "command": lambda: panel._open_picker("NPC")},
        {"key": "pc", "icon": icons["pc"], "tooltip": "Add PC", "command": lambda: panel._open_picker("PC")},
        {"key": "creature", "icon": icons["creat"], "tooltip": "Add Creature", "command": lambda: panel._open_picker("Creature")},
        {"key": "base", "icon": icons["marker"], "tooltip": "Add Base", "command": lambda: panel._open_picker("Base")},
        {"key": "place", "icon": icons["marker"], "tooltip": "Add Place", "command": lambda: panel._open_picker("Place")},
        {"key": "map", "icon": icons["marker"], "tooltip": "Add Map", "command": lambda: panel._open_picker("Map")},
    ]
    entity_dropdown = IconDropdown(entities_body, entity_actions, default_key="npc", button_size=(24, 24), show_arrow=False)
    entity_dropdown.pack(side="top", anchor="center", padx=0, pady=3)

    panel.marker_type_filter_menu = create_slim_option_menu(
        entities_body,
        values=MARKER_TYPE_FILTER_LABELS,
        command=panel._on_marker_type_filter_change,
    )
    panel.marker_type_filter_menu.set(getattr(panel, "marker_type_filter", "All Types") or "All Types")
    add_stacked_control(entities_body, "Marker", panel.marker_type_filter_menu)

    root = panel.winfo_toplevel()
    root.bind("[", lambda e: panel._change_brush(-4), add="+")
    root.bind("]", lambda e: panel._change_brush(+4), add="+")

    if hasattr(panel, "_update_fog_button_states"):
        panel._update_fog_button_states()

    return palette


def _build_floating_drawing_toolbar(self):
    """Build a compact floating palette for fog and drawing controls."""
    return build_maptool_floating_drawing_toolbar(self)
