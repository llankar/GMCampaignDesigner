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
        font=("Segoe UI", 44, "bold"),
        fg=fg,
        bg=bg
    ).pack(pady=(10, 5))

    # Fields container
    body = tk.Frame(root, bg=bg)
    body.pack(fill="both", expand=True, padx=40, pady=10)

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

    # Render each requested field (skip Portrait which we handled above)
    for field in fields:
        if field.lower() == "portrait":
            continue
        val = item.get(field, "")
        val = _decode_longtext_payload(val)
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
        tk.Label(row, text=f"{field}:", font=("Segoe UI", 22, "bold"), fg=fg, bg=bg).pack(side="top", anchor="w")
        tk.Label(row, text=val, font=("Segoe UI", 20), fg=fg, bg=bg, justify="left", wraplength=sw-120).pack(side="top", anchor="w")

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

