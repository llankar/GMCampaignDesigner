"""Platform-aware transparent window host for the fixed GM Table overlay."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

import customtkinter as ctk


TRANSPARENT_COLOR = "#010203"


@dataclass(frozen=True)
class TransparencySupport:
    """Describes the transparency mode selected for an overlay window."""

    mode: str
    true_transparency: bool
    reason: str = ""


class TransparentOverlayWindow:
    """A toplevel layer anchored over a master widget.

    Tk's regular child widgets cannot be truly translucent on every platform. This
    host keeps the fixed-overlay controls in a dedicated borderless ``Toplevel``
    positioned over the GM table, then uses the best transparency option Tk offers
    on the current windowing system. If true transparent colors are unavailable,
    it gracefully falls back to an opaque toplevel whose child widgets still use
    the pre-blended overlay colors from ``style.py``.
    """

    def __init__(self, master: tk.Widget, *, background: str) -> None:
        self.master = master
        self._width = 1
        self._visible = False
        self._place_options: dict[str, object] = {}
        self.window = tk.Toplevel(master.winfo_toplevel())
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(background=TRANSPARENT_COLOR)
        self.window.transient(master.winfo_toplevel())
        self.support = self._configure_transparency()
        # Keep the full-window host painted with Tk's transparent color.
        # Opaque overlay chrome belongs on the controls/cards themselves; if the
        # root shell uses the blended panel background it covers the entire
        # Toplevel and defeats the transparent-color window configuration.
        self.shell = ctk.CTkFrame(
            self.window,
            fg_color=TRANSPARENT_COLOR,
            corner_radius=0,
            border_width=0,
        )
        self.shell.place(x=0, y=0, relheight=1.0, relwidth=1.0)
        self._bind_anchor_events()

    def _configure_transparency(self) -> TransparencySupport:
        try:
            self.window.attributes("-transparentcolor", TRANSPARENT_COLOR)
            return TransparencySupport("transparentcolor", True)
        except tk.TclError as exc:
            try:
                self.window.attributes("-alpha", 0.80)
                return TransparencySupport("alpha", True, str(exc))
            except tk.TclError as alpha_exc:
                return TransparencySupport("fallback", False, str(alpha_exc))

    def _bind_anchor_events(self) -> None:
        for widget in {self.master, self.master.winfo_toplevel()}:
            try:
                widget.bind("<Configure>", self._on_anchor_configure, add="+")
                widget.bind("<Destroy>", self._on_anchor_destroy, add="+")
            except tk.TclError:
                pass

    def _on_anchor_configure(self, _event: object = None) -> None:
        if self._visible:
            self._apply_geometry()

    def _on_anchor_destroy(self, event: object = None) -> None:
        if event is not None and getattr(event, "widget", None) is self.master:
            self.destroy()

    def configure(self, **kwargs: object) -> None:
        if "width" in kwargs:
            self._width = max(1, int(kwargs["width"] or 1))
        shell_kwargs = {k: v for k, v in kwargs.items() if k != "width"}
        if "fg_color" in shell_kwargs:
            shell_kwargs["fg_color"] = TRANSPARENT_COLOR
        self.shell.configure(**shell_kwargs)

    def place_configure(self, **kwargs: object) -> None:
        self._place_options.update(kwargs)
        self._width = max(1, int(kwargs.get("width") or self._width))
        self._visible = True
        self._apply_geometry()
        self.window.deiconify()

    def place(self, **kwargs: object) -> None:
        self.place_configure(**kwargs)

    def place_forget(self) -> None:
        self._visible = False
        self.window.withdraw()

    def _apply_geometry(self) -> None:
        try:
            self.master.update_idletasks()
            x = self.master.winfo_rootx() + int(self._place_options.get("x") or 0)
            y = self.master.winfo_rooty() + int(self._place_options.get("y") or 0)
            height = max(1, self.master.winfo_height())
        except tk.TclError:
            return
        self.window.geometry(f"{self._width}x{height}+{x}+{y}")

    def lift(self) -> None:
        self.window.lift()

    def destroy(self) -> None:
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def update_idletasks(self) -> None:
        self.window.update_idletasks()
