from __future__ import annotations

import tkinter as tk
from typing import Any

from PIL import ImageOps, ImageTk


def prepare_menu_image(icon: Any) -> tk.PhotoImage | None:
    """Convert CTk/PIL-backed icons into a Tk-compatible image for native menus."""
    if icon is None:
        return None

    if isinstance(icon, tk.PhotoImage):
        return icon

    pil_image = _extract_pil_image(icon)
    if pil_image is None:
        return None

    target_size = getattr(icon, "_size", None)
    if target_size and hasattr(pil_image, "size") and pil_image.size != target_size:
        pil_image = ImageOps.contain(pil_image.copy(), target_size)

    return ImageTk.PhotoImage(pil_image)


def _extract_pil_image(icon: Any):
    for attr_name in ("_light_image", "_dark_image", "light_image", "dark_image", "_image"):
        image = getattr(icon, attr_name, None)
        if image is not None:
            return image
    return None
