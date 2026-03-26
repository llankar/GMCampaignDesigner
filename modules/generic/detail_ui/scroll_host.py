import tkinter as tk
import customtkinter as ctk


def build_scroll_host(parent):
    """Create a resilient vertically scrollable host frame."""
    if not hasattr(parent, "tk"):
        fallback = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        fallback.pack(fill="both", expand=True)
        return fallback

    shell = ctk.CTkFrame(parent, fg_color="transparent")
    shell.pack(fill="both", expand=True)

    background = "#1f1f1f"
    if hasattr(parent, "cget"):
        try:
            fg_color = parent.cget("fg_color")
            if isinstance(fg_color, str) and fg_color:
                background = fg_color
        except Exception:
            pass

    try:
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
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(event):
        try:
            canvas.itemconfigure(window_id, width=max(1, event.width))
        except Exception:
            pass
        _on_content_configure()

    def _on_mousewheel(event):
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

    content._scroll_canvas = canvas
    content._scrollbar = scrollbar
    return content
