"""Geometry helpers for detail UI window."""
from modules.helpers.logging_helper import log_function


@log_function
def apply_fullscreen_top_left(window, *, min_width: int = 1000, min_height: int = 600) -> str:
    """Expand a detail window to the full screen and anchor it at (0, 0)."""

    screen_width = max(int(window.winfo_screenwidth()), 1)
    screen_height = max(int(window.winfo_screenheight()), 1)

    geometry = f"{screen_width}x{screen_height}+0+0"
    window.geometry(geometry)
    window.minsize(min(min_width, screen_width), min(min_height, screen_height))
    return geometry
