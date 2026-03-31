"""Panel for audio mood."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk


def build_mood_panel(parent: Any, *, section: str, on_select: Callable[[str], None], on_add: Callable[[str], None], on_rename: Callable[[str], None], on_remove: Callable[[str], None]) -> dict[str, Any]:
    """Build mood panel."""
    frame = ctk.CTkFrame(parent)
    frame.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
    frame.grid_rowconfigure(1, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(frame, text="Moods", font=("Segoe UI", 16, "bold")).grid(
        row=0, column=0, sticky="w", padx=8, pady=(8, 4)
    )

    mood_list = tk.Listbox(frame, exportselection=False, activestyle="none", height=14)
    mood_list.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
    mood_list.bind("<<ListboxSelect>>", lambda _evt, s=section: on_select(s))

    mood_scroll = tk.Scrollbar(frame, orient="vertical", command=mood_list.yview)
    mood_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
    mood_list.configure(yscrollcommand=mood_scroll.set)

    buttons = ctk.CTkFrame(frame)
    buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
    buttons.grid_columnconfigure((0, 1), weight=1)

    ctk.CTkButton(buttons, text="Add Mood", command=lambda s=section: on_add(s)).grid(
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

    return {"frame": frame, "mood_list": mood_list}
