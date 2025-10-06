import os
import json
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from modules.ui.image_viewer import _get_monitors
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.text_helpers import format_multiline_text
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_warning,
    log_module_import,
)

log_module_import(__name__)

@log_function
def show_entity_on_second_screen(item, title, fields):
    log_info(f"Showing entity on second screen: {title}", func_name="show_entity_on_second_screen")
    """Open a fullscreen window on the second monitor displaying selected fields of an entity.

    - item: dict of entity data
    - title: string for main heading
    - fields: list of field names to display (may include 'Portrait')
    """
    monitors = _get_monitors()
    if not monitors:
        log_warning("No monitors available for second screen display", func_name="show_entity_on_second_screen")
        return
    target = monitors[1] if len(monitors) > 1 else monitors[0]
    sx, sy, sw, sh = target

    win = ctk.CTkToplevel()
    win.title(str(title or "Entity"))
    win.geometry(f"{sw}x{sh}+{sx}+{sy}")
    win.update_idletasks()

    bg = "white"
    fg = "black"
    root = tk.Frame(win, bg=bg)
    root.pack(fill="both", expand=True)

    # Optional portrait at top if requested
    portrait_label = None
    if any(f.lower() == "portrait" for f in fields):
        portrait_rel = item.get("Portrait", "")
        portrait_abs = None
        if portrait_rel:
            if os.path.isabs(portrait_rel) and os.path.exists(portrait_rel):
                portrait_abs = portrait_rel
            else:
                candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_rel)
                if os.path.exists(candidate):
                    portrait_abs = candidate
        if portrait_abs:
            try:
                img = Image.open(portrait_abs)
                max_w = min(sw - 120, 800)
                max_h = min(sh // 3, 400)
                ow, oh = img.size
                scale = min(max_w / ow, max_h / oh, 1)
                if scale < 1:
                    img = img.resize((int(ow*scale), int(oh*scale)), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                portrait_label = tk.Label(root, image=photo, bg=bg)
                portrait_label.image = photo
                portrait_label.pack(pady=20)
            except Exception:
                portrait_label = None

    # Title
    tk.Label(
        root,
        text=str(title or ""),
        font=("Segoe UI", 32, "bold"),
        fg=fg,
        bg=bg
    ).pack(pady=(10, 5))

    # Fields container with vertical scrolling
    body_container = tk.Frame(root, bg=bg)
    body_container.pack(fill="both", expand=True, padx=40, pady=10)

    canvas = tk.Canvas(body_container, bg=bg, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = tk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scrollbar.set)

    body = tk.Frame(canvas, bg=bg)
    body_window = canvas.create_window((0, 0), window=body, anchor="nw")

    def _update_scroll_region(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _resize_body(event):
        canvas.itemconfig(body_window, width=event.width)

    body.bind("<Configure>", _update_scroll_region)
    canvas.bind("<Configure>", _resize_body)

    def _on_mousewheel(event):
        """Scroll the canvas when the mouse wheel is used."""
        if event.delta:
            # Windows and macOS provide an event delta
            direction = -1 if event.delta > 0 else 1
        else:
            # Linux uses button numbers for wheel events
            if event.num == 4:
                direction = -1
            elif event.num == 5:
                direction = 1
            else:
                return "break"
        canvas.yview_scroll(direction, "units")
        return "break"

    def _focus_canvas(_event):
        canvas.focus_set()

    def _bind_mousewheel(widget):
        """Ensure the mouse wheel scrolls the canvas from anywhere in the window."""
        widget.bind("<Enter>", _focus_canvas, add="+")
        widget.bind("<MouseWheel>", _on_mousewheel, add="+")
        widget.bind("<Button-4>", _on_mousewheel, add="+")
        widget.bind("<Button-5>", _on_mousewheel, add="+")

    for widget in (win, root, body_container, canvas, body):
        _bind_mousewheel(widget)

    def _decode_longtext_payload(raw_value):
        """Return a structured value for longtext JSON blobs stored as strings."""
        if not isinstance(raw_value, str):
            return raw_value
        stripped = raw_value.strip()
        if not stripped.startswith("{"):
            return raw_value
        if '"text"' not in stripped and '"formatting"' not in stripped:
            return raw_value
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return raw_value
        if isinstance(decoded, dict) and ("text" in decoded or "formatting" in decoded):
            return decoded
        return raw_value

    def _normalise_scene_entries(raw_scenes):
        """Return a list of scene dictionaries from stored payloads."""
        if raw_scenes is None:
            return []
        # Stored as {"Scenes": [...]} or JSON string? handle both
        if isinstance(raw_scenes, str):
            stripped = raw_scenes.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    decoded = json.loads(stripped)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, dict) and isinstance(decoded.get("Scenes"), list):
                    return decoded.get("Scenes")
                if isinstance(decoded, list):
                    return decoded
            # fall back to treating as single text scene
            return [raw_scenes]
        if isinstance(raw_scenes, dict):
            if isinstance(raw_scenes.get("Scenes"), list):
                return raw_scenes.get("Scenes")
            # Sometimes scenes payload is a mapping representing one scene
            return [raw_scenes]
        if isinstance(raw_scenes, (list, tuple, set)):
            return list(raw_scenes)
        return [raw_scenes]

    def _coerce_name_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(v).strip() for v in value if str(v).strip()]
        text = str(value or "")
        if not text.strip():
            return []
        parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
        return parts or [text.strip()]

    def _coerce_scene_text(value):
        value = _decode_longtext_payload(value)
        if isinstance(value, list):
            rendered_parts = []
            for part in value:
                part = _decode_longtext_payload(part)
                if isinstance(part, dict):
                    rendered_parts.append(format_multiline_text(part))
                elif part:
                    rendered_parts.append(str(part))
            return "\n".join(rendered_parts)
        if isinstance(value, dict):
            return format_multiline_text(value)
        return format_multiline_text(value) if value else ""

    def _render_scenes_section(parent, payload):
        scenes = _normalise_scene_entries(payload)
        if not scenes:
            return False

        section = tk.Frame(parent, bg=bg)
        section.pack(fill="x", anchor="w", pady=(10, 5))
        tk.Label(
            section,
            text="Scenes",
            font=("Segoe UI", 26, "bold"),
            fg=fg,
            bg=bg
        ).pack(anchor="w", pady=(0, 6))

        for idx, raw_scene in enumerate(scenes, start=1):
            scene = raw_scene if isinstance(raw_scene, dict) else {"Text": raw_scene}

            # Heading
            title = ""
            for key in ("Title", "Scene", "Name", "Heading"):
                if scene.get(key):
                    title = str(scene.get(key)).strip()
                    if title:
                        break
            header_parts = [f"Scene {idx}"]
            if title:
                header_parts.append(title)
            tk.Label(
                section,
                text=": ".join(header_parts),
                font=("Segoe UI", 20, "bold"),
                fg=fg,
                bg=bg
            ).pack(anchor="w", pady=(2, 2))

            # Body text (Text/Summary/etc.)
            body_text = ""
            for key in ("Text", "Summary", "Description", "Body", "Notes", "Gist"):
                if scene.get(key):
                    body_text = _coerce_scene_text(scene.get(key))
                    if body_text:
                        break
            if body_text:
                tk.Label(
                    section,
                    text=body_text,
                    font=("Segoe UI", 16),
                    fg=fg,
                    bg=bg,
                    justify="left",
                    wraplength=sw - 160
                ).pack(anchor="w", pady=(0, 4))

            # Related entities (NPCs, Places, etc.)
            related_fields = []
            for label, key in (("NPCs", "NPCs"), ("Creatures", "Creatures"), ("Places", "Places"), ("Maps", "Maps")):
                names = _coerce_name_list(scene.get(key))
                if names:
                    related_fields.append((label, names))
            for label, names in related_fields:
                tk.Label(
                    section,
                    text=f"{label}: {', '.join(names)}",
                    font=("Segoe UI", 14, "italic"),
                    fg=fg,
                    bg=bg,
                    justify="left",
                    wraplength=sw - 160
                ).pack(anchor="w", pady=(0, 2))

        return True

    # Render each requested field (skip Portrait which we handled above)
    for field in fields:
        if field.lower() == "portrait":
            continue
        val = item.get(field, "")
        val = _decode_longtext_payload(val)
        if field.lower() == "scenes":
            if _render_scenes_section(body, val):
                continue
        if isinstance(val, dict):
            # Show rich text as multiline text content
            val = format_multiline_text(val)
        elif isinstance(val, list):
            val = ", ".join(str(v) for v in val if v is not None)
        else:
            val = str(val or "")

        if not val:
            continue

        row = tk.Frame(body, bg=bg)
        row.pack(fill="x", anchor="w", pady=6)
        tk.Label(row, text=f"{field}:", font=("Segoe UI", 18, "bold"), fg=fg, bg=bg).pack(side="top", anchor="w")
        tk.Label(row, text=val, font=("Segoe UI", 16), fg=fg, bg=bg, justify="left", wraplength=sw-120).pack(side="top", anchor="w")

    # Close on click or Escape
    win.bind("<Button-1>", lambda e: win.destroy())
    win.bind("<Escape>", lambda e: win.destroy())

    # Ensure front
    win.lift()
    try:
        win.attributes("-topmost", True)
        win.after(100, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

