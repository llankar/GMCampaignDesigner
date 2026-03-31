"""Utilities for detail UI scroll host."""

import tkinter as tk
import customtkinter as ctk


def _resolve_canvas_background(widget) -> str:
    """Return a Tk-compatible solid background color for the scroll canvas."""
    fallback = "#1f1f1f"
    current = widget

    while current is not None:
        # Keep looping while current is available.
        if hasattr(current, "cget"):
            # Handle the branch where hasattr(current, 'cget').
            try:
                fg_color = current.cget("fg_color")
            except Exception:
                fg_color = None
            if isinstance(fg_color, (list, tuple)) and fg_color:
                appearance = ctk.get_appearance_mode()
                index = 1 if appearance == "Dark" else 0
                fg_color = fg_color[min(index, len(fg_color) - 1)]
            if isinstance(fg_color, str):
                # Handle the branch where isinstance(fg_color, str).
                candidate = fg_color.strip()
                if candidate and candidate.lower() != "transparent":
                    return candidate
        current = getattr(current, "master", None)

    return fallback


def build_scroll_host(parent):
    """Create a resilient vertically scrollable host frame."""
    if not hasattr(parent, "tk"):
        fallback = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        fallback.pack(fill="both", expand=True)
        return fallback

    shell = ctk.CTkFrame(parent, fg_color="transparent")
    shell.pack(fill="both", expand=True)

    background = _resolve_canvas_background(parent)

    try:
        # Keep scroll host resilient if this step fails.
        canvas = tk.Canvas(shell, highlightthickness=0, bd=0, background=background)
    except Exception:
        fallback = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        fallback.pack(fill="both", expand=True)
        return fallback
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = ctk.CTkScrollbar(shell, orientation="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y", padx=(8, 0))
    canvas.configure(yscrollcommand=scrollbar.set)

    content = ctk.CTkFrame(canvas, fg_color="transparent")
    window_id = canvas.create_window((0, 0), window=content, anchor="nw")

    def _on_content_configure(_event=None):
        """Handle content configure."""
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(event):
        """Handle canvas configure."""
        try:
            canvas.itemconfigure(window_id, width=max(1, event.width))
        except Exception:
            pass
        _on_content_configure()

    def _on_mousewheel(event):
        """Handle mousewheel."""
        delta = getattr(event, "delta", 0)
        if delta:
            direction = -1 if delta > 0 else 1
        elif getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            return

        try:
            canvas.yview_scroll(direction, "units")
        except Exception:
            return
        return "break"

    content.bind("<Configure>", _on_content_configure, add="+")
    canvas.bind("<Configure>", _on_canvas_configure, add="+")

    for widget in (parent, shell, canvas, content):
        widget.bind("<MouseWheel>", _on_mousewheel, add="+")
        widget.bind("<Button-4>", _on_mousewheel, add="+")
        widget.bind("<Button-5>", _on_mousewheel, add="+")

    content._scrollable_frame = content
    content._parent_canvas = canvas
    content._scroll_canvas = canvas
    content._scrollbar = scrollbar
    return content
