# modules/ui/image_viewer.py
import os, ctypes
from modules.helpers.config_helper import ConfigHelper
from ctypes import wintypes
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

# max size for the popup (same as in generic_list_view)
MAX_PORTRAIT_SIZE = (1024, 1024)

def _get_monitors():
    """Return list of (x, y, width, height)."""
    monitors = []
    def _enum(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        monitors.append((rect.left, rect.top,
                        rect.right - rect.left,
                        rect.bottom - rect.top))
        return True
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    ctypes.windll.user32.EnumDisplayMonitors(
        0, 0, MonitorEnumProc(_enum), 0)
    return monitors

def show_portrait(path, title=None):
    """
    Display a full‑screen CTkToplevel showing the image at `path`.
    Clicking anywhere closes the window.
    """
    if path and not os.path.isabs(path):
        candidate = os.path.join(ConfigHelper.get_campaign_dir(), path)
        if os.path.exists(candidate):
            path = candidate
    if not path or not os.path.exists(path):
        tk.messagebox.showerror("Error", "No valid portrait available.")
        return

    try:
        img = Image.open(path)
    except Exception as e:
        tk.messagebox.showerror("Error", f"Failed to load image: {e}")
        return

    # scale down if too large
    ow, oh = img.size
    mw, mh = MAX_PORTRAIT_SIZE
    scale = min(mw/ow, mh/oh, 1)
    if scale < 1:
        img = img.resize((int(ow*scale), int(oh*scale)),
                        Image.Resampling.LANCZOS)

    photo = ImageTk.PhotoImage(img)

    # pick a monitor (second if available)
    monitors = _get_monitors()
    target = monitors[1] if len(monitors) > 1 else monitors[0]
    sx, sy, sw, sh = target

    win = ctk.CTkToplevel()
    win.title(title or os.path.basename(path))
    win.geometry(f"{sw}x{sh}+{sx}+{sy}")
    win.update_idletasks()

    # white background frame
    content = tk.Frame(win, bg="white")
    content.pack(fill="both", expand=True)

    # optional title label
    if title:
        tk.Label(
            content,
            text=title,
            font=("Arial", 40, "bold"),
            fg="black",
            bg="white"
        ).pack(pady=20)

    lbl = tk.Label(content, image=photo, bg="white")
    lbl.image = photo
    lbl.pack(expand=True)

    # click to close
    win.bind("<Button-1>", lambda e: win.destroy())