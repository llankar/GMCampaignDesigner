"""View for world map toolbar."""

import tkinter as tk
import customtkinter as ctk
from modules.helpers.logging_helper import log_module_import
from modules.maps.marker_types import MARKER_TYPE_FILTER_LABELS
from modules.maps.utils.icon_loader import load_icon
from modules.ui.icon_dropdown import IconDropdown

log_module_import(__name__)


def build_world_map_toolbar(panel) -> None:
    """Build world map toolbar."""
    section_tracker = {"count": 0}
    horizontal_spacing = 6
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

    marker_section = _create_collapsible_section(toolbar, "Marker")
    ctk.CTkLabel(marker_section, text="Type:", font=("Segoe UI", 14, "bold")).pack(
        side="left", padx=(8, 6), pady=6
    )
    panel.marker_type_filter_menu = ctk.CTkOptionMenu(
        marker_section,
        values=MARKER_TYPE_FILTER_LABELS,
        command=panel._on_marker_type_filter_change,
        width=130,
    )
    panel.marker_type_filter_menu.set(getattr(panel, "marker_type_filter", "All Types") or "All Types")
    _pack_control(panel.marker_type_filter_menu, trailing=6, pady=6)

    fog_section = _create_collapsible_section(toolbar, "Fog")
    fog_actions = [
        {"key": "clear", "icon": icons["clear"], "tooltip": "Clear Fog", "command": panel.clear_fog},
        {"key": "reset", "icon": icons["reset"], "tooltip": "Reset Fog", "command": panel.reset_fog},
    ]
    fog_dropdown = IconDropdown(fog_section, fog_actions, default_key="clear")
    _pack_control(fog_dropdown, trailing=4)
    panel._global_fog_dropdown = fog_dropdown

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
