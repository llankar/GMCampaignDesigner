"""Panel for audio category."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk


def build_category_panel(parent: Any, *, section: str, on_select: Callable[[str], None], on_add: Callable[[str], None], on_rename: Callable[[str], None], on_remove: Callable[[str], None]) -> dict[str, Any]:
    """Build category panel."""
    frame = ctk.CTkFrame(parent)
    frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
    frame.grid_rowconfigure(1, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(frame, text="Types", font=("Segoe UI", 16, "bold")).grid(
        row=0, column=0, sticky="w", padx=8, pady=(8, 4)
    )

    category_list = tk.Listbox(frame, exportselection=False, activestyle="none", height=14)
    category_list.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
    category_list.bind("<<ListboxSelect>>", lambda _evt, s=section: on_select(s))

    cat_scroll = tk.Scrollbar(frame, orient="vertical", command=category_list.yview)
    cat_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
    category_list.configure(yscrollcommand=cat_scroll.set)

    directories_var = tk.StringVar(value="Folders: none")
    directories_label = ctk.CTkLabel(
        frame,
        textvariable=directories_var,
        justify="left",
        wraplength=220,
        anchor="w",
    )
    directories_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))

    buttons = ctk.CTkFrame(frame)
    buttons.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
    buttons.grid_columnconfigure((0, 1), weight=1)

    ctk.CTkButton(buttons, text="Add Type", command=lambda s=section: on_add(s)).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ctk.CTkButton(buttons, text="Rename", command=lambda s=section: on_rename(s)).grid(
        row=0, column=1, sticky="ew", padx=(4, 0)
    )
    ctk.CTkButton(
        buttons,
        text="Remove",
        fg_color="#8b1d1d",
        hover_color="#6f1414",
        command=lambda s=section: on_remove(s),
    ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    return {
        "frame": frame,
        "category_list": category_list,
        "directories_var": directories_var,
        "directories_label": directories_label,
    }
