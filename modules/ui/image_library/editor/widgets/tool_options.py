"""Tool options and action bar for image editor."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk


class ToolOptionsBar(ctk.CTkFrame):
    """Bottom controls including transform actions and brush/image settings."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        active_tool_var: tk.StringVar,
        brush_size_var: tk.DoubleVar,
        brush_opacity_var: tk.DoubleVar,
        brush_color_var: tk.StringVar,
        brightness_var: tk.DoubleVar,
        contrast_var: tk.DoubleVar,
        on_rotate_left: Callable[[], None],
        on_rotate_right: Callable[[], None],
        on_mirror: Callable[[], None],
        on_flip: Callable[[], None],
        on_reset: Callable[[], None],
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
        on_brightness_change: Callable[[float], None],
        on_contrast_change: Callable[[float], None],
        on_cut: Callable[[], None],
        on_copy: Callable[[], None],
        on_paste: Callable[[], None],
        on_save: Callable[[], None],
        on_save_as: Callable[[], None],
        on_tool_changed: Callable[[str], None],
    ) -> None:
        super().__init__(master)

        ctk.CTkButton(self, text="Rotate Left", command=on_rotate_left).grid(row=0, column=0, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Rotate Right", command=on_rotate_right).grid(row=0, column=1, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Mirror", command=on_mirror).grid(row=0, column=2, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Flip", command=on_flip).grid(row=0, column=3, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Reset", command=on_reset).grid(row=0, column=4, padx=6, pady=(10, 6))

        self.undo_button = ctk.CTkButton(self, text="Undo", command=on_undo)
        self.undo_button.grid(row=0, column=5, padx=6, pady=(10, 6))
        self.redo_button = ctk.CTkButton(self, text="Redo", command=on_redo)
        self.redo_button.grid(row=0, column=6, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Cut", command=on_cut).grid(row=0, column=7, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Copy", command=on_copy).grid(row=0, column=8, padx=6, pady=(10, 6))
        ctk.CTkButton(self, text="Paste", command=on_paste).grid(row=0, column=9, padx=6, pady=(10, 6))

        ctk.CTkLabel(self, text="Tool").grid(row=1, column=0, padx=(10, 6), pady=4, sticky="e")
        tool_selector = ctk.CTkSegmentedButton(
            self,
            values=["Paint", "Eraser", "Rectangle", "Ellipse", "Select", "Magic Select"],
            variable=active_tool_var,
            command=on_tool_changed,
            width=520,
        )
        tool_selector.grid(row=1, column=1, columnspan=2, padx=4, pady=4, sticky="w")

        ctk.CTkLabel(self, text="Brush Size").grid(row=1, column=3, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            self,
            from_=1,
            to=128,
            number_of_steps=127,
            variable=brush_size_var,
            command=lambda _value: None,
            width=220,
        ).grid(row=1, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkLabel(self, text="Brush Opacity").grid(row=2, column=0, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            self,
            from_=0.05,
            to=1.0,
            number_of_steps=19,
            variable=brush_opacity_var,
            command=lambda _value: None,
            width=220,
        ).grid(row=2, column=1, columnspan=2, padx=2, pady=4, sticky="w")

        self._brush_color_preview = ctk.CTkButton(
            self,
            text="Brush Color",
            width=120,
            command=self._choose_brush_color,
        )
        self._brush_color_preview.grid(row=3, column=0, padx=(10, 6), pady=4, sticky="e")
        self._brush_color_var = brush_color_var
        self._brush_color_var.trace_add("write", lambda *_args: self._refresh_brush_color_preview())
        self._refresh_brush_color_preview()

        ctk.CTkLabel(self, text="Brightness").grid(row=2, column=3, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            self,
            from_=0.2,
            to=2.0,
            number_of_steps=36,
            variable=brightness_var,
            command=on_brightness_change,
            width=220,
        ).grid(row=2, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkLabel(self, text="Contrast").grid(row=3, column=3, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            self,
            from_=0.2,
            to=2.0,
            number_of_steps=36,
            variable=contrast_var,
            command=on_contrast_change,
            width=220,
        ).grid(row=3, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkButton(self, text="Save", command=on_save).grid(row=4, column=4, padx=6, pady=(10, 10), sticky="e")
        ctk.CTkButton(self, text="Save As", command=on_save_as).grid(row=4, column=5, padx=(0, 10), pady=(10, 10), sticky="w")

    def _choose_brush_color(self) -> None:
        initial = self._brush_color_var.get() or "#000000"
        selected = colorchooser.askcolor(initialcolor=initial, parent=self)
        hex_color = selected[1]
        if hex_color:
            self._brush_color_var.set(hex_color)

    def _refresh_brush_color_preview(self) -> None:
        color = self._brush_color_var.get() or "#000000"
        self._brush_color_preview.configure(fg_color=color, hover_color=color)
