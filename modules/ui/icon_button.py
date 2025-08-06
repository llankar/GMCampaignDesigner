import tkinter as tk
import customtkinter as ctk
from modules.ui.tooltip import ToolTip

def create_icon_button(parent, icon, tooltip_text, command):
    container = tk.Frame(parent, bg="#2B2B2B")

    btn = ctk.CTkButton(
        container,
        text="",
        image=icon,
        command=command,
        width=10,
        height=10,
        corner_radius=12,
        fg_color="#0077CC",
        hover_color="#005fa3",
        border_width=1,
        border_color="#005fa3"
    )
    btn.pack()

    ToolTip(btn, tooltip_text)  # ✅ Tooltip tied to the actual button, not frame

    return container
