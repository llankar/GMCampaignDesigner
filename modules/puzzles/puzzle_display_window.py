import os
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Union

import customtkinter as ctk
from PIL import Image
from tkinter import messagebox, ttk

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_module_import, log_warning
from modules.helpers.rtf_rendering import render_rtf_to_text_widget
from modules.helpers.text_helpers import format_multiline_text

log_module_import(__name__)

try:
    RESAMPLE_MODE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1 fallback
    RESAMPLE_MODE = Image.LANCZOS


def _resolve_handout_path(handout_value: str) -> str:
    if not handout_value:
        return ""
    if os.path.isabs(handout_value):
        return handout_value
    return os.path.join(ConfigHelper.get_campaign_dir(), handout_value)


def _open_handout_file(path: str) -> None:
    if not path:
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        log_info(
            f"Opened puzzle handout '{path}'.",
            func_name="puzzle_display_window._open_handout_file",
        )
    except Exception as exc:
        log_warning(
            f"Failed to open puzzle handout '{path}': {exc}",
            func_name="puzzle_display_window._open_handout_file",
        )
        messagebox.showerror("Handout", f"Failed to open the file:\n{exc}")


ParentWidget = Union[ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkToplevel]


def _add_section_title(parent: ParentWidget, title: str) -> None:
    ctk.CTkLabel(parent, text=title, font=("Arial", 18, "bold")).pack(anchor="w", pady=(12, 4))


def _add_short_text(parent: ParentWidget, label: str, value: Any) -> None:
    ctk.CTkLabel(parent, text=f"{label}:", font=("Arial", 14, "bold")).pack(anchor="w")
    ctk.CTkLabel(
        parent,
        text=format_multiline_text(value),
        font=("Arial", 14),
        wraplength=800,
        justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 6))


def _add_longtext(parent: ParentWidget, label: str, value: Any) -> None:
    ctk.CTkLabel(parent, text=f"{label}:", font=("Arial", 14, "bold")).pack(anchor="w")
    box = ctk.CTkTextbox(parent, wrap="word")
    render_rtf_to_text_widget(box, value)
    box.pack(fill="x", padx=10, pady=(0, 8))

    def update_height() -> None:
        text_widget = getattr(box, "_textbox", box)
        lines = int(text_widget.count("1.0", "end", "lines")[0])
        font = tkfont.Font(font=text_widget.cget("font"))
        line_px = font.metrics("linespace")
        box.configure(height=max(3, lines + 1) * line_px)
        box.configure(state="disabled")

    box.after_idle(update_height)


def _add_handout_section(parent: ParentWidget, window: ctk.CTkToplevel, handout_value: str) -> None:
    ctk.CTkLabel(parent, text="Handout:", font=("Arial", 14, "bold")).pack(anchor="w")
    if not handout_value:
        ctk.CTkLabel(parent, text="No handout file assigned.", font=("Arial", 13)).pack(
            anchor="w", padx=10, pady=(0, 8)
        )
        return

    resolved = _resolve_handout_path(handout_value)
    if not resolved or not os.path.exists(resolved):
        ctk.CTkLabel(
            parent,
            text=f"Handout not found: {resolved or handout_value}",
            font=("Arial", 13),
            text_color="#FF8888",
        ).pack(anchor="w", padx=10, pady=(0, 8))
        return

    image_obj = None
    try:
        with Image.open(resolved) as img:
            image_obj = img.copy()
        image_obj.thumbnail((900, 700), RESAMPLE_MODE)
    except Exception:
        image_obj = None

    if image_obj is not None:
        preview_frame = ctk.CTkScrollableFrame(parent, height=360)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        ctk_image = ctk.CTkImage(light_image=image_obj, dark_image=image_obj, size=image_obj.size)
        if not hasattr(window, "_handout_images"):
            window._handout_images = []
        window._handout_images.append(ctk_image)
        ctk.CTkLabel(preview_frame, image=ctk_image, text="").pack(anchor="center", pady=6)
        path_label = ctk.CTkLabel(
            parent,
            text=resolved,
            font=("Arial", 12),
            text_color="#4A90E2",
            cursor="hand2",
        )
        path_label.pack(anchor="w", padx=10, pady=(0, 8))
        path_label.bind("<Button-1>", lambda _event: _open_handout_file(resolved))
        return

    link = ctk.CTkLabel(
        parent,
        text=resolved,
        font=("Arial", 12),
        text_color="#4A90E2",
        cursor="hand2",
    )
    link.pack(anchor="w", padx=10, pady=(0, 8))
    link.bind("<Button-1>", lambda _event: _open_handout_file(resolved))


def open_puzzle_display(parent: ParentWidget, puzzle_item: dict) -> ctk.CTkToplevel | None:
    if not puzzle_item:
        return None

    name = puzzle_item.get("Name") or "Puzzle"
    window = ctk.CTkToplevel(parent)
    window.title(f"Puzzle: {name}")
    window.geometry("900x720")
    window.minsize(720, 520)

    content = ctk.CTkScrollableFrame(window)
    content.pack(fill="both", expand=True, padx=20, pady=20)

    _add_section_title(content, "Puzzle Overview")
    _add_short_text(content, "Name", name)

    difficulty_tags = puzzle_item.get("DifficultyTags", [])
    if isinstance(difficulty_tags, list):
        difficulty_text = ", ".join(str(tag) for tag in difficulty_tags if tag)
    else:
        difficulty_text = str(difficulty_tags)
    _add_short_text(content, "Difficulty Tags", difficulty_text)

    ttk.Separator(content, orient="horizontal").pack(fill="x", pady=8)
    _add_section_title(content, "Description")
    _add_longtext(content, "Description", puzzle_item.get("Description", ""))

    ttk.Separator(content, orient="horizontal").pack(fill="x", pady=8)
    _add_section_title(content, "Solution")
    _add_longtext(content, "Solution", puzzle_item.get("Solution", ""))

    ttk.Separator(content, orient="horizontal").pack(fill="x", pady=8)
    _add_section_title(content, "Handout Text")
    _add_longtext(content, "Handout Text", puzzle_item.get("HandoutText", ""))

    ttk.Separator(content, orient="horizontal").pack(fill="x", pady=8)
    _add_section_title(content, "Handout")
    _add_handout_section(content, window, puzzle_item.get("Handout", ""))

    return window
