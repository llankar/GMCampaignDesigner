"""One-column layout helpers for the map floating toolbar."""

import customtkinter as ctk

PALETTE_BG = "#151515"
SECTION_BG = "#1f1f1f"
BORDER = "#3f3f3f"
TEXT_MUTED = "#cfcfcf"
SLIDER_WIDTH = 76
CONTROL_FONT_SIZE = 11


def create_section(parent, title):
    """Create a titled toolbar section that stacks controls vertically."""
    section = ctk.CTkFrame(parent, fg_color=SECTION_BG, border_width=1, border_color="#303030", corner_radius=9)
    section.pack(side="top", fill="x", padx=0, pady=(3, 0))
    ctk.CTkLabel(section, text=title, text_color=TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold")).pack(
        side="top", fill="x", padx=5, pady=(4, 0)
    )
    body = ctk.CTkFrame(section, fg_color="transparent")
    body.pack(side="top", fill="x", padx=4, pady=(1, 5))
    return body


def create_row(parent):
    """Create a full-width row in the toolbar's single column."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(side="top", fill="x", pady=1)
    return row


def add_small_label(parent, text):
    """Add a muted label above a control."""
    ctk.CTkLabel(parent, text=text, text_color=TEXT_MUTED).pack(side="top", fill="x", padx=0, pady=(2, 0))


def add_stacked_control(parent, label, widget, *, pady=(0, 4)):
    """Place a label and a naturally-sized widget in the toolbar column."""
    row = create_row(parent)
    add_small_label(row, label)
    widget.pack(side="top", anchor="center", padx=0, pady=pady)
    return row
