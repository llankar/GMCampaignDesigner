"""Dialogs for GM Table desk annotation styling."""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk

from modules.scenarios.gm_table.workspace import TABLE_PALETTE


DEFAULT_DRAW_COLOR = "#1F2937"
DEFAULT_TEXT_COLOR = "#241A10"
DEFAULT_TEXT_SIZE = 18
DEFAULT_STROKE_WIDTH = 3
TEXT_SIZE_OPTIONS = (12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48, 56, 64)
STROKE_WIDTH_OPTIONS = (2, 3, 4, 5, 6, 8, 10, 12)


def _normalize_hex_color(value: str | None, fallback: str) -> str:
    """Return a Tk-compatible hex color value."""
    candidate = str(value or "").strip()
    if len(candidate) == 7 and candidate.startswith("#"):
        try:
            int(candidate[1:], 16)
            return candidate.upper()
        except ValueError:
            return fallback
    return fallback


def _coerce_option(value, options: tuple[int, ...], fallback: int) -> int:
    """Coerce a numeric option to one of the allowed values."""
    try:
        numeric = int(value)
    except Exception:
        return fallback
    return numeric if numeric in options else fallback


class DeskAnnotationStyleDialog(ctk.CTkToplevel):
    """Collect color and size choices for GM Table desk annotations."""

    def __init__(self, master, *, tool: str, initial_style: dict | None = None) -> None:
        super().__init__(master)
        self.tool = "text" if str(tool).lower() == "text" else "draw"
        style = initial_style or {}
        self.result: dict | None = None
        self.title("Desk Text Style" if self.tool == "text" else "Draw Style")
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)

        default_color = DEFAULT_TEXT_COLOR if self.tool == "text" else DEFAULT_DRAW_COLOR
        self.color_var = tk.StringVar(
            value=_normalize_hex_color(style.get("fill"), default_color)
        )
        self.text_size_var = tk.StringVar(
            value=str(_coerce_option(style.get("font_size"), TEXT_SIZE_OPTIONS, DEFAULT_TEXT_SIZE))
        )
        self.stroke_width_var = tk.StringVar(
            value=str(_coerce_option(style.get("width"), STROKE_WIDTH_OPTIONS, DEFAULT_STROKE_WIDTH))
        )

        self._build_body()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())
        self.bind("<Return>", lambda _event: self._apply())
        self.after_idle(self._bring_to_front)

    def _build_body(self) -> None:
        container = ctk.CTkFrame(self, fg_color=TABLE_PALETTE["table_alt"], corner_radius=18)
        container.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        container.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            container,
            text="Color",
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=(14, 10), pady=(14, 8), sticky="w")
        self.color_preview = ctk.CTkButton(
            container,
            text="Selected",
            width=132,
            height=30,
            fg_color=self.color_var.get(),
            hover_color=self.color_var.get(),
            text_color="#FFFFFF",
            command=self._choose_color,
        )
        self.color_preview.grid(row=0, column=1, padx=(0, 14), pady=(14, 8), sticky="ew")

        if self.tool == "text":
            ctk.CTkLabel(
                container,
                text="Text size",
                text_color=TABLE_PALETTE["text"],
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=1, column=0, padx=(14, 10), pady=8, sticky="w")
            ctk.CTkOptionMenu(
                container,
                values=[str(size) for size in TEXT_SIZE_OPTIONS],
                variable=self.text_size_var,
                width=132,
                fg_color=TABLE_PALETTE["table_chip"],
                button_color=TABLE_PALETTE["accent"],
                button_hover_color="#D97706",
                dropdown_fg_color=TABLE_PALETTE["table_alt"],
                dropdown_hover_color="#283146",
                text_color=TABLE_PALETTE["text"],
                dropdown_text_color=TABLE_PALETTE["text"],
            ).grid(row=1, column=1, padx=(0, 14), pady=8, sticky="ew")
        else:
            ctk.CTkLabel(
                container,
                text="Line size",
                text_color=TABLE_PALETTE["text"],
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=1, column=0, padx=(14, 10), pady=8, sticky="w")
            ctk.CTkOptionMenu(
                container,
                values=[str(width) for width in STROKE_WIDTH_OPTIONS],
                variable=self.stroke_width_var,
                width=132,
                fg_color=TABLE_PALETTE["table_chip"],
                button_color=TABLE_PALETTE["accent"],
                button_hover_color="#D97706",
                dropdown_fg_color=TABLE_PALETTE["table_alt"],
                dropdown_hover_color="#283146",
                text_color=TABLE_PALETTE["text"],
                dropdown_text_color=TABLE_PALETTE["text"],
            ).grid(row=1, column=1, padx=(0, 14), pady=8, sticky="ew")

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=2, padx=14, pady=(12, 14), sticky="e")
        ctk.CTkButton(
            actions,
            text="Cancel",
            width=86,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            command=self._cancel,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Use Tool",
            width=98,
            fg_color=TABLE_PALETTE["accent"],
            hover_color="#D97706",
            text_color="#10131B",
            command=self._apply,
        ).pack(side="left")

    def _choose_color(self) -> None:
        color = colorchooser.askcolor(
            color=self.color_var.get(),
            title="Choose desk annotation color",
            parent=self,
        )[1]
        if color:
            normalized = _normalize_hex_color(color, self.color_var.get())
            self.color_var.set(normalized)
            self.color_preview.configure(text="Selected", fg_color=normalized, hover_color=normalized)

    def _apply(self) -> None:
        self.result = {"fill": self.color_var.get()}
        if self.tool == "text":
            self.result["font_size"] = _coerce_option(
                self.text_size_var.get(), TEXT_SIZE_OPTIONS, DEFAULT_TEXT_SIZE
            )
        else:
            self.result["width"] = _coerce_option(
                self.stroke_width_var.get(), STROKE_WIDTH_OPTIONS, DEFAULT_STROKE_WIDTH
            )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _bring_to_front(self) -> None:
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))


def ask_desk_annotation_style(master, *, tool: str, initial_style: dict | None = None) -> dict | None:
    """Open a modal style dialog and return the chosen annotation style."""
    dialog = DeskAnnotationStyleDialog(master, tool=tool, initial_style=initial_style)
    master.wait_window(dialog)
    return dialog.result
