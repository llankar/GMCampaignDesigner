import tkinter as tk
import customtkinter as ctk
from modules.helpers.logging_helper import log_module_import

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
