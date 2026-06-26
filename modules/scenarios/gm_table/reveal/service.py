"""Shared reveal actions for GM Table player-facing displays."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from typing import Any, Iterable

import customtkinter as ctk

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_warning
from modules.helpers.portrait_helper import resolve_portrait_candidate
from modules.helpers.text_helpers import (
    deserialize_possible_json,
    format_multiline_text,
)
from modules.ui.image_viewer import show_portrait, _get_monitors

_IMAGE_PANEL_KINDS = {"image"}
_MAP_PANEL_KINDS = {"world_map", "map_tool"}
_SUPPORTED_PANEL_KINDS = {*_IMAGE_PANEL_KINDS, *_MAP_PANEL_KINDS, "entity"}
_TITLE_KEYS = ("Name", "Title", "Scenario", "Heading")
_GM_ONLY_TOKENS = (
    "gm",
    "dm",
    "secret",
    "secrets",
    "private",
    "hidden",
    "spoiler",
    "solution",
    "answer",
    "notes",
    "internal",
)
_SKIP_EXACT_KEYS = {
    "id",
    "uuid",
    "created",
    "created_at",
    "updated",
    "updated_at",
    "tags",
    "portrait",
    "portraits",
    "image",
    "images",
    "image_path",
    "fogmaskpath",
    "tokens",
}


@dataclass(slots=True)
class RevealResult:
    """Outcome of a reveal attempt."""

    ok: bool
    message: str = ""


def is_reveal_supported(kind: str, state: dict | None = None) -> bool:
    """Return whether a GM Table panel kind can offer a Reveal action."""
    _ = state
    normalized = str(kind or "").strip()
    if normalized in _SUPPORTED_PANEL_KINDS:
        return True
    if normalized == "handouts":
        return True
    return False


def reveal_image(
    path: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    animation: str | None = None,
    quiet: bool = False,
) -> RevealResult:
    """Reveal image-like content via the existing full-screen image reveal utility."""
    resolved = resolve_portrait_candidate(path, ConfigHelper.get_campaign_dir())
    if not resolved:
        message = "No revealable image was found for this panel."
        if not quiet:
            messagebox.showwarning("Reveal", message)
        return RevealResult(False, message)
    window = show_portrait(resolved, title=title, subtitle=subtitle, animation=animation)
    if window is None:
        message = "The image reveal could not be opened."
        return RevealResult(False, message)
    log_info(f"Revealed image '{resolved}'.", func_name="gm_table.reveal.reveal_image")
    return RevealResult(True)


def reveal_handout(handout: Any, *, animation: str | None = None) -> RevealResult:
    """Reveal a collected handout item."""
    path = str(getattr(handout, "path", "") or "").strip()
    title = str(getattr(handout, "title", "") or "").strip() or Path(path).name
    subtitle = str(getattr(handout, "subtitle", "") or "").strip() or None
    return reveal_image(path, title=title, subtitle=subtitle, animation=animation)


def reveal_map_payload(payload: object, *, title: str | None = None) -> RevealResult:
    """Reveal a map-capable payload, preferring its native player display."""
    if payload is None:
        message = "No map panel is available to reveal."
        messagebox.showinfo("Reveal", message)
        return RevealResult(False, message)

    opener = getattr(payload, "open_player_display", None)
    if callable(opener):
        before = _current_toplevel(payload)
        opener()
        after = _current_toplevel(payload)
        if after is not None or before is not None:
            log_info("Revealed map via native player display.", func_name="gm_table.reveal.reveal_map_payload")
            return RevealResult(True)
        message = "The map player display is not available for the current map."
        messagebox.showinfo("Reveal", message)
        return RevealResult(False, message)

    current_map = getattr(payload, "current_map", None)
    if isinstance(current_map, dict):
        image_path = str(current_map.get("Image") or current_map.get("image") or "").strip()
        map_title = str(current_map.get("Name") or title or "Map").strip()
        if image_path:
            return reveal_image(image_path, title=map_title, subtitle="Map")

    message = "This map panel does not expose a player display."
    messagebox.showinfo("Reveal", message)
    return RevealResult(False, message)


def reveal_entity(entity_type: str, item: dict, *, title: str | None = None) -> RevealResult:
    """Reveal player-safe text for an entity, clue, or information record."""
    if not isinstance(item, dict) or not item:
        message = "No entity content is available to reveal."
        _show_reveal_info(message)
        return RevealResult(False, message)

    display_title = str(title or _entity_title(item) or entity_type or "Reveal").strip()
    sections = list(_player_safe_sections(item))
    if not sections:
        message = "No player-safe fields were found to reveal."
        _show_reveal_info(message)
        return RevealResult(False, message)

    window = _show_text_reveal(display_title, str(entity_type or "").strip(), sections)
    if window is None:
        message = "No player display is available for this reveal."
        _show_reveal_info(message)
        return RevealResult(False, message)
    log_info(f"Revealed text entity '{display_title}'.", func_name="gm_table.reveal.reveal_entity")
    return RevealResult(True)


def _show_reveal_info(message: str) -> None:
    """Show a reveal info dialog when Tk is available."""
    try:
        messagebox.showinfo("Reveal", message)
    except tk.TclError as exc:
        log_warning(
            f"Unable to show reveal dialog: {exc}",
            func_name="gm_table.reveal._show_reveal_info",
        )


def _current_toplevel(payload: object):
    for attr in ("_player_view_window", "player_display_window", "player_window"):
        candidate = getattr(payload, attr, None)
        if candidate is not None:
            return candidate
    return None


def _entity_title(item: dict) -> str:
    for key in _TITLE_KEYS:
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _is_gm_only_key(key: str) -> bool:
    normalized = str(key or "").strip().casefold().replace(" ", "_").replace("-", "_")
    if normalized in _SKIP_EXACT_KEYS:
        return True
    return any(token in normalized for token in _GM_ONLY_TOKENS)


def _player_safe_sections(item: dict) -> Iterable[tuple[str, str]]:
    for key, value in item.items():
        label = str(key or "").strip()
        if not label or _is_gm_only_key(label):
            continue
        text = _format_reveal_value(value)
        if not text:
            continue
        yield label, text


def _format_reveal_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        decoded = deserialize_possible_json(stripped)
        if decoded != stripped:
            return _format_reveal_value(decoded)
        return stripped
    if isinstance(value, dict):
        if "text" in value or "formatting" in value:
            return format_multiline_text(value).strip()
        parts = []
        for child_key, child_value in value.items():
            if _is_gm_only_key(str(child_key)):
                continue
            child_text = _format_reveal_value(child_value)
            if child_text:
                parts.append(f"{child_key}: {child_text}")
        return "\n".join(parts).strip()
    if isinstance(value, (list, tuple, set)):
        parts = [_format_reveal_value(part) for part in value]
        return "\n".join(part for part in parts if part).strip()
    return str(value).strip()


def _show_text_reveal(title: str, subtitle: str, sections: list[tuple[str, str]]):
    try:
        monitors = _get_monitors()
    except tk.TclError as exc:
        log_warning(
            f"Unable to detect monitors for text reveal: {exc}",
            func_name="gm_table.reveal._show_text_reveal",
        )
        return None
    if not monitors:
        log_warning("No monitors detected for text reveal", func_name="gm_table.reveal._show_text_reveal")
        return None
    monitor_x, monitor_y, monitor_width, monitor_height = monitors[1] if len(monitors) > 1 else monitors[0]

    win = None
    try:
        win = ctk.CTkToplevel()
        win.title(title or "Reveal")
        win.geometry(f"{monitor_width}x{monitor_height}+{monitor_x}+{monitor_y}")
        try:
            win.configure(fg_color="#F8FAFC")
        except Exception:
            pass

        root = tk.Frame(win, bg="#F8FAFC")
        root.pack(fill="both", expand=True)
        header = tk.Frame(root, bg="#0F172A")
        header.pack(fill="x")
        if subtitle:
            tk.Label(
                header,
                text=subtitle.upper(),
                font=("Segoe UI", 16, "bold"),
                fg="#FBBF24",
                bg="#0F172A",
            ).pack(anchor="w", padx=48, pady=(30, 0))
        tk.Label(
            header,
            text=title,
            font=("Segoe UI", 34, "bold"),
            fg="#F8FAFC",
            bg="#0F172A",
            justify="left",
            wraplength=max(480, monitor_width - 120),
        ).pack(anchor="w", padx=48, pady=(6, 30))

        body_container = tk.Frame(root, bg="#F8FAFC")
        body_container.pack(fill="both", expand=True, padx=42, pady=28)
        canvas = tk.Canvas(body_container, bg="#F8FAFC", highlightthickness=0)
        scrollbar = tk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        body = tk.Frame(canvas, bg="#F8FAFC")
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _update_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _resize(event):
            canvas.itemconfig(window_id, width=event.width)

        body.bind("<Configure>", _update_scroll)
        canvas.bind("<Configure>", _resize)

        for label, text in sections:
            section = tk.Frame(body, bg="#F8FAFC")
            section.pack(fill="x", anchor="w", pady=(0, 20))
            tk.Label(
                section,
                text=label,
                font=("Segoe UI", 20, "bold"),
                fg="#0F172A",
                bg="#F8FAFC",
            ).pack(anchor="w")
            tk.Label(
                section,
                text=text,
                font=("Segoe UI", 17),
                fg="#1E293B",
                bg="#F8FAFC",
                justify="left",
                wraplength=max(420, monitor_width - 140),
            ).pack(anchor="w", pady=(4, 0))

        def _close(_event=None):
            win.destroy()
            return "break"

        for sequence in ("<Escape>", "<Button-1>"):
            win.bind(sequence, _close)
        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass
        return win
    except tk.TclError as exc:
        log_warning(
            f"Unable to create text reveal window: {exc}",
            func_name="gm_table.reveal._show_text_reveal",
        )
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass
        return None
