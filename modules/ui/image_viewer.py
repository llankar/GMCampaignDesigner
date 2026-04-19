"""Viewer for image reveals."""

import ctypes
import os
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_module_import,
    log_warning,
)
from modules.helpers.portrait_helper import resolve_portrait_path

log_module_import(__name__)

MAX_PORTRAIT_SIZE = (1024, 1024)
_REVEAL_BG = "#05070D"
_REVEAL_TITLE = "#F4F7FB"
_REVEAL_SUBTITLE = "#D7B46A"
DEFAULT_REVEAL_ANIMATION = "fade"
REVEAL_ANIMATION_OPTIONS = (
    ("Fade", "fade"),
    ("Zoom In", "zoom"),
    ("Drift Up", "drift_up"),
    ("Curtain", "curtain"),
)
_REVEAL_ANIMATIONS = {value for _label, value in REVEAL_ANIMATION_OPTIONS}
_REVEAL_ANIMATION_ALIASES = {
    label.casefold().replace("-", "_").replace(" ", "_"): value
    for label, value in REVEAL_ANIMATION_OPTIONS
}
_REVEAL_ANIMATION_ALIASES.update(
    {
        "zoom_in": "zoom",
        "drift": "drift_up",
    }
)
_FADE_ALPHA_STEPS = (0.0, 0.18, 0.35, 0.52, 0.68, 0.82, 0.92, 1.0)
_FADE_DELAY_MS = 28
_ZOOM_START_SCALE = 0.9
_DRIFT_START_OFFSET = 42


def _clean_text(value):
    text = str(value or "").strip()
    return text or None


def normalize_reveal_animation(value):
    animation = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if animation in _REVEAL_ANIMATIONS:
        return animation
    if animation in _REVEAL_ANIMATION_ALIASES:
        return _REVEAL_ANIMATION_ALIASES[animation]
    return DEFAULT_REVEAL_ANIMATION


@log_function
def _configure_single_monitor_overlay(win, monitors):
    """Keep portrait window visible on single-screen setups."""
    if len(monitors) != 1:
        return
    try:
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
    except Exception:
        return


@log_function
def _fallback_primary_monitor():
    """Build a safe single-monitor fallback from Tk screen metrics."""
    probe = tk.Tk()
    probe.withdraw()
    try:
        width = int(probe.winfo_screenwidth())
        height = int(probe.winfo_screenheight())
    finally:
        probe.destroy()
    if width <= 0 or height <= 0:
        return []
    return [(0, 0, width, height)]


@log_function
def _get_monitors():
    """Return list of (x, y, width, height)."""
    monitors = []
    if os.name != "nt":
        return _fallback_primary_monitor()

    def _enum(h_monitor, hdc_monitor, rect_ptr, data):
        """Internal helper for enum."""
        _ = h_monitor, hdc_monitor, data
        rect = rect_ptr.contents
        monitors.append(
            (
                rect.left,
                rect.top,
                rect.right - rect.left,
                rect.bottom - rect.top,
            )
        )
        return True

    try:
        monitor_enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, monitor_enum_proc(_enum), 0)
    except Exception:
        return _fallback_primary_monitor()

    return monitors or _fallback_primary_monitor()


def _target_monitor(monitors):
    return monitors[1] if len(monitors) > 1 else monitors[0]


def _reserved_header_space(title=None, subtitle=None):
    if title and subtitle:
        return 180
    if title or subtitle:
        return 128
    return 56


def _resize_for_reveal(image, monitor_width, monitor_height, *, title=None, subtitle=None):
    """Scale image down to fit within the reveal viewport."""
    original_width, original_height = image.size
    reserved = _reserved_header_space(title=title, subtitle=subtitle)
    max_width = int(monitor_width * 0.84)
    max_height = int(monitor_height * 0.84) - reserved
    if max_width <= 0 or max_height <= 0:
        max_width, max_height = MAX_PORTRAIT_SIZE

    scale = min(max_width / original_width, max_height / original_height, 1)
    if scale >= 1:
        return image

    resized_size = (
        max(1, int(original_width * scale)),
        max(1, int(original_height * scale)),
    )
    return image.resize(resized_size, Image.Resampling.LANCZOS)


def _destroy_window(win, _event=None):
    try:
        win.destroy()
    except Exception:
        return "break"
    return "break"


def _window_exists(win):
    try:
        return bool(win.winfo_exists())
    except Exception:
        return False


def _bind_close_controls(win):
    close = lambda event=None: _destroy_window(win, event)
    for sequence in ("<Button-1>", "<Escape>", "<Return>", "<space>"):
        win.bind(sequence, close)
    try:
        win.protocol("WM_DELETE_WINDOW", close)
    except Exception:
        pass
    return close


def _load_reveal_image(path):
    with Image.open(path) as source:
        return source.copy()


def _build_reveal_content(win, photo, *, title=None, subtitle=None):
    content = tk.Frame(win, bg=_REVEAL_BG, highlightthickness=0, bd=0)
    content.pack(fill="both", expand=True)

    stage = tk.Frame(content, bg=_REVEAL_BG, highlightthickness=0, bd=0)
    stage.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0, y=0)

    if title or subtitle:
        metadata = tk.Frame(stage, bg=_REVEAL_BG, highlightthickness=0, bd=0)
        metadata.pack(fill="x", pady=(36, 14))

        if subtitle:
            tk.Label(
                metadata,
                text=subtitle.upper(),
                font=("Arial", 16, "bold"),
                fg=_REVEAL_SUBTITLE,
                bg=_REVEAL_BG,
            ).pack()

        if title:
            tk.Label(
                metadata,
                text=title,
                font=("Arial", 34, "bold"),
                fg=_REVEAL_TITLE,
                bg=_REVEAL_BG,
                justify="center",
            ).pack(pady=(8 if subtitle else 0, 0))

    image_frame = tk.Frame(stage, bg=_REVEAL_BG, highlightthickness=0, bd=0)
    image_frame.pack(fill="both", expand=True, padx=48, pady=(0, 40))

    image_label = tk.Label(
        image_frame,
        image=photo,
        bg=_REVEAL_BG,
        bd=0,
        highlightthickness=0,
    )
    image_label.image = photo
    image_label.pack(expand=True)
    content._reveal_stage = stage
    content._reveal_image_label = image_label
    content._reveal_photo = photo
    return content


def _build_zoom_frames(image, alpha_steps):
    if not alpha_steps:
        return []
    step_count = len(alpha_steps)
    if step_count == 1:
        scales = (1.0,)
    else:
        scales = tuple(
            _ZOOM_START_SCALE + ((1.0 - _ZOOM_START_SCALE) * (index / (step_count - 1)))
            for index in range(step_count)
        )

    photos = []
    for scale in scales:
        if scale >= 0.999:
            render = image
        else:
            render = image.resize(
                (
                    max(1, int(image.size[0] * scale)),
                    max(1, int(image.size[1] * scale)),
                ),
                Image.Resampling.LANCZOS,
            )
        photos.append(ImageTk.PhotoImage(render))
    return photos


def _ensure_curtain_overlays(content):
    overlays = getattr(content, "_reveal_curtain_overlays", None)
    if overlays:
        return overlays

    left = tk.Frame(content, bg=_REVEAL_BG, highlightthickness=0, bd=0)
    right = tk.Frame(content, bg=_REVEAL_BG, highlightthickness=0, bd=0)
    overlays = (left, right)
    content._reveal_curtain_overlays = overlays
    return overlays


def _set_curtain_position(content, progress):
    left, right = _ensure_curtain_overlays(content)
    try:
        width = int(content.winfo_width())
    except Exception:
        width = 0
    if width <= 1:
        try:
            width = int(content.winfo_reqwidth())
        except Exception:
            width = 0
    if width <= 0:
        width = MAX_PORTRAIT_SIZE[0]

    panel_width = max(0, int((width / 2) * (1.0 - progress)))
    if panel_width <= 0:
        left.place_forget()
        right.place_forget()
        return

    left.place(x=0, y=0, width=panel_width, relheight=1.0)
    right.place(relx=1.0, x=-panel_width, y=0, width=panel_width, relheight=1.0)


def _schedule_reveal_animation(
    win,
    content,
    *,
    animation=None,
    image=None,
    alpha_steps=_FADE_ALPHA_STEPS,
    delay_ms=_FADE_DELAY_MS,
):
    animation = normalize_reveal_animation(animation)
    stage = getattr(content, "_reveal_stage", None)
    image_label = getattr(content, "_reveal_image_label", None)

    zoom_frames = []
    if animation == "zoom" and image is not None and image_label is not None:
        zoom_frames = _build_zoom_frames(image, alpha_steps)
        if zoom_frames:
            image_label.configure(image=zoom_frames[0])
            image_label.image = zoom_frames[0]
            content._reveal_zoom_frames = zoom_frames
    elif animation == "drift_up" and stage is not None:
        stage.place_configure(y=_DRIFT_START_OFFSET)
    elif animation == "curtain":
        _set_curtain_position(content, 0.0)

    if not alpha_steps:
        return

    alpha_supported = True
    try:
        win.attributes("-alpha", float(alpha_steps[0]))
    except Exception:
        alpha_supported = False

    step_count = len(alpha_steps)

    def _apply(index):
        nonlocal alpha_supported
        if not _window_exists(win):
            return
        if alpha_supported:
            try:
                win.attributes("-alpha", float(alpha_steps[index]))
            except Exception:
                alpha_supported = False

        progress = 1.0 if step_count <= 1 else index / (step_count - 1)
        if animation == "zoom" and zoom_frames and image_label is not None:
            current = zoom_frames[index]
            image_label.configure(image=current)
            image_label.image = current
        elif animation == "drift_up" and stage is not None:
            offset = int(round(_DRIFT_START_OFFSET * (1.0 - progress)))
            stage.place_configure(y=offset)
        elif animation == "curtain":
            _set_curtain_position(content, progress)

        if index + 1 < step_count:
            try:
                win.after(delay_ms, lambda: _apply(index + 1))
            except Exception:
                return

    if len(alpha_steps) > 1:
        try:
            win.after(delay_ms, lambda: _apply(1))
        except Exception:
            return


@log_function
def show_portrait(path, title=None, subtitle=None, animation=None):
    """Display a dark full-screen reveal for an image."""
    title = _clean_text(title)
    subtitle = _clean_text(subtitle)
    animation = normalize_reveal_animation(animation)
    log_info(f"Showing portrait: {path}", func_name="show_portrait")

    resolved = resolve_portrait_path(path, ConfigHelper.get_campaign_dir())
    if not resolved or not os.path.exists(resolved):
        log_warning(f"Portrait path missing or invalid: {path}", func_name="show_portrait")
        messagebox.showerror("Error", "No valid portrait available.")
        return None

    try:
        image = _load_reveal_image(resolved)
    except Exception as exc:
        log_warning(f"Failed to load portrait {resolved}: {exc}", func_name="show_portrait")
        messagebox.showerror("Error", f"Failed to load image: {exc}")
        return None

    monitors = _get_monitors()
    if not monitors:
        log_warning("No monitors detected for portrait viewer", func_name="show_portrait")
        messagebox.showerror("Error", "Unable to detect any display.")
        return None

    monitor_x, monitor_y, monitor_width, monitor_height = _target_monitor(monitors)
    image = _resize_for_reveal(
        image,
        monitor_width,
        monitor_height,
        title=title,
        subtitle=subtitle,
    )
    photo = ImageTk.PhotoImage(image)

    win = ctk.CTkToplevel()
    win.title(title or Path(resolved).name)
    try:
        win.configure(fg_color=_REVEAL_BG)
    except Exception:
        pass
    try:
        win.overrideredirect(True)
    except Exception:
        pass
    win.geometry(f"{monitor_width}x{monitor_height}+{monitor_x}+{monitor_y}")
    win.update_idletasks()
    try:
        win.lift()
        win.focus_force()
    except Exception:
        pass
    _configure_single_monitor_overlay(win, monitors)
    _bind_close_controls(win)
    content = _build_reveal_content(win, photo, title=title, subtitle=subtitle)
    _schedule_reveal_animation(win, content, animation=animation, image=image)
    return win
