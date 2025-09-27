import tkinter as tk
import customtkinter as ctk
from modules.ui.tooltip import ToolTip
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

def create_icon_button(parent, icon, tooltip_text, command):
    container = tk.Frame(parent, bg="#2B2B2B")

    has_icon = icon is not None
    if has_icon:
        display_text = ""
        width = 10
        height = 10
    else:
        display_text = tooltip_text if len(tooltip_text) <= 18 else tooltip_text[:17] + "..."
        width = 160
        height = 48

    btn = ctk.CTkButton(
        container,
        text=display_text,
        image=icon,
        command=command,
        width=width,
        height=height,
        corner_radius=12,
        fg_color="#0077CC",
        hover_color="#005fa3",
        border_width=1,
        border_color="#005fa3"
    )

    if not has_icon:
        btn.configure(font=("Segoe UI", 14, "bold"))

    btn.pack(fill="both", expand=True)

    # Expose the underlying button widget so callers can adjust its
    # configuration after creation (for example, to reflect toggled states).
    # This keeps backwards compatibility by still returning the container.
    container.icon_button = btn
    container.button = btn
    ToolTip(btn, tooltip_text)
    return container

