"""One-column layout helpers for the map floating toolbar."""

import customtkinter as ctk

# Palette toned to the Map Sheet / parchment skin (forest teal + vivid emerald).
PALETTE_BG = "#091A12"
SECTION_BG = "#0D2018"
BORDER = "#175C38"
TEXT_MUTED = "#6DCFA0"
ACCENT = "#10C97C"
SLIDER_WIDTH = 76
CONTROL_FONT_SIZE = 11


def create_section(parent, title):
    """Create a titled toolbar section that stacks controls vertically."""
    section = ctk.CTkFrame(parent, fg_color=SECTION_BG, border_width=1, border_color=BORDER, corner_radius=9)
    section.pack(side="top", fill="x", padx=0, pady=(3, 0))
    ctk.CTkLabel(section, text=title, text_color=ACCENT, font=ctk.CTkFont(size=11, weight="bold")).pack(
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
