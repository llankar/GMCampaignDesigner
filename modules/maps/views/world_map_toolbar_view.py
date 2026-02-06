import tkinter as tk
import customtkinter as ctk
from modules.helpers.logging_helper import log_module_import
from modules.maps.utils.icon_loader import load_icon
from modules.ui.icon_dropdown import IconDropdown

log_module_import(__name__)


def build_world_map_toolbar(panel) -> None:
    section_tracker = {"count": 0}
    horizontal_spacing = 6
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
            width=110,
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

    toolbar_container = ctk.CTkFrame(panel, fg_color="#101429")
    toolbar_container.pack(side="top", fill="x", padx=12, pady=(12, 0))

    toolbar_height = 70
    toolbar = ctk.CTkScrollableFrame(
        toolbar_container,
        orientation="horizontal",
        height=toolbar_height,
        fg_color="transparent",
    )
    toolbar.pack(fill="x", expand=True)

    icons = {
        "add": load_icon(panel, "assets/icons/brush.png", (32, 32)),
        "rem": load_icon(panel, "assets/icons/eraser.png", (32, 32)),
        "clear": load_icon(panel, "assets/icons/empty.png", (32, 32)),
        "reset": load_icon(panel, "assets/icons/full.png", (32, 32)),
    }

    map_section = _create_collapsible_section(toolbar, "Map")
    ctk.CTkLabel(map_section, text="Map:", font=("Segoe UI", 14, "bold")).pack(side="left", padx=(8, 6), pady=6)
    panel.map_selector = ctk.CTkOptionMenu(
        map_section,
        values=panel.map_names,
        command=panel._on_map_selected,
        width=240,
    )
    _pack_control(panel.map_selector, trailing=10, pady=6)

    panel.set_default_button = ctk.CTkButton(
        map_section,
        text="Set as default",
        width=140,
        command=panel._set_default_map,
    )
    _pack_control(panel.set_default_button, trailing=10)

    panel.back_button = ctk.CTkButton(
        map_section,
        text="Back",
        width=120,
        command=panel.navigate_back,
        state=ctk.DISABLED,
    )
    _pack_control(panel.back_button, trailing=6)

    fog_section = _create_collapsible_section(toolbar, "Fog")
    panel._fog_button_default_style = {
        "fg_color": "#0077CC",
        "hover_color": "#005fa3",
        "border_color": "#005fa3",
        "border_width": 1,
    }
    panel._fog_button_active_style = {
        "fg_color": "#004c80",
        "hover_color": "#004c80",
        "border_color": "#d7263d",
        "border_width": 3,
    }
    panel._fog_buttons = {}

    fog_actions = [
        {"key": "add", "icon": icons["add"], "tooltip": "Add Fog", "command": lambda: panel._set_fog("add")},
        {"key": "rem", "icon": icons["rem"], "tooltip": "Remove Fog", "command": lambda: panel._set_fog("rem")},
        {"key": "add_rect", "icon": icons["add"], "tooltip": "Add Fog Rectangle", "command": lambda: panel._set_fog("add_rect")},
        {"key": "rem_rect", "icon": icons["rem"], "tooltip": "Remove Fog Rectangle", "command": lambda: panel._set_fog("rem_rect")},
        {"key": "clear", "icon": icons["clear"], "tooltip": "Clear Fog", "command": panel.clear_fog},
        {"key": "reset", "icon": icons["reset"], "tooltip": "Reset Fog", "command": panel.reset_fog},
    ]

    fog_dropdown = IconDropdown(fog_section, fog_actions, default_key="add")
    _pack_control(fog_dropdown, trailing=4)
    panel._fog_buttons.update(fog_dropdown.option_buttons)
    panel._fog_dropdown = fog_dropdown

    shape_label = ctk.CTkLabel(fog_section, text="Fog Shape:")
    _pack_control(shape_label, leading=8, trailing=4)
    panel.shape_menu = ctk.CTkOptionMenu(
        fog_section,
        values=["Rectangle", "Circle"],
        command=panel._on_brush_shape_change,
        width=110,
    )
    panel.shape_menu.set("Rectangle")
    _pack_control(panel.shape_menu, trailing=4)

    size_label = ctk.CTkLabel(fog_section, text="Brush Size")
    _pack_control(size_label, leading=4, trailing=4)
    brush_size_options = list(getattr(panel, "brush_size_options", list(range(4, 129, 4))))
    current_brush_size = int(getattr(panel, "brush_size", brush_size_options[0] if brush_size_options else 32))
    if current_brush_size not in brush_size_options:
        brush_size_options.append(current_brush_size)
        brush_size_options = sorted(set(brush_size_options))
    panel.brush_size_options = list(brush_size_options)
    brush_size_values = [str(size) for size in panel.brush_size_options]
    panel.brush_size_menu = ctk.CTkOptionMenu(
        fog_section,
        values=brush_size_values,
        command=panel._on_brush_size_change,
        width=90,
    )
    panel.brush_size_menu.set(str(current_brush_size))
    _pack_control(panel.brush_size_menu, leading=0, trailing=4, pady=6)

    root = panel.winfo_toplevel()
    root.bind("[", lambda e: panel._change_brush(-4), add="+")
    root.bind("]", lambda e: panel._change_brush(+4), add="+")

    entity_section = _create_collapsible_section(toolbar, "Entities")
    panel.add_npc_button = ctk.CTkButton(entity_section, text="Add NPC", command=lambda: panel._open_picker("NPC"))
    panel.add_pc_button = ctk.CTkButton(entity_section, text="Add PC", command=lambda: panel._open_picker("PC"))
    panel.add_creature_button = ctk.CTkButton(
        entity_section,
        text="Add Creature",
        command=lambda: panel._open_picker("Creature"),
    )
    panel.add_place_button = ctk.CTkButton(entity_section, text="Add Place", command=lambda: panel._open_picker("Place"))
    panel.add_map_button = ctk.CTkButton(entity_section, text="Add Map", command=lambda: panel._open_picker("Map"))

    for button in (
        panel.add_npc_button,
        panel.add_pc_button,
        panel.add_creature_button,
        panel.add_place_button,
        panel.add_map_button,
    ):
        _pack_control(button, trailing=6)

    action_section = _create_collapsible_section(toolbar, "Actions")
    panel.save_button = ctk.CTkButton(action_section, text="Save", width=120, command=panel._persist_tokens)
    _pack_control(panel.save_button, trailing=10)

    panel.player_view_button = ctk.CTkButton(
        action_section,
        text="Open Player Display",
        width=170,
        command=panel.open_player_display,
        state=ctk.DISABLED,
    )
    _pack_control(panel.player_view_button, trailing=10)

    panel.map_tool_button = ctk.CTkButton(
        action_section,
        text="Open in Map Tool",
        width=160,
        command=panel._open_in_map_tool,
        state=ctk.DISABLED,
    )
    _pack_control(panel.map_tool_button, trailing=10)

    panel.chatbot_button = ctk.CTkButton(action_section, text="Chatbot", width=140, command=panel.open_chatbot)
    _pack_control(panel.chatbot_button, trailing=6)

    panel._update_fog_button_states()
