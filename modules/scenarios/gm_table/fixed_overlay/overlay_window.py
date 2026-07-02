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
        self._geometry_retry_id: str | None = None
        self._place_options: dict[str, object] = {}
        self._last_geometry_failure_reason = ""
        self._destroyed = False
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
            self.ensure_visible()

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

    @property
    def last_geometry_failure_reason(self) -> str:
        """Return the last reason geometry could not be applied safely."""
        return self._last_geometry_failure_reason

    def place_configure(self, **kwargs: object) -> None:
        """Store placement options without changing logical visibility."""
        self._place_options.update(kwargs)
        self._width = max(1, int(kwargs.get("width") or self._width))

    def place(self, **kwargs: object) -> None:
        self.place_configure(**kwargs)

    def place_forget(self) -> None:
        self.hide()

    def show(self) -> bool:
        """Mark the overlay visible and map it once anchor geometry is ready."""
        self._visible = True
        return self.ensure_visible()

    def hide(self) -> None:
        """Mark the overlay hidden and withdraw the toplevel immediately."""
        self._visible = False
        self._cancel_geometry_retry()
        try:
            self.window.withdraw()
        except tk.TclError:
            pass

    def is_geometry_ready(self) -> bool:
        """Return whether the anchor can provide useful geometry right now."""
        try:
            self.master.update_idletasks()
            mapped = bool(self.master.winfo_ismapped())
            width = self.master.winfo_width()
            height = self.master.winfo_height()
        except tk.TclError as exc:
            self._last_geometry_failure_reason = f"anchor unavailable: {exc}"
            return False
        if not mapped:
            self._last_geometry_failure_reason = "anchor is unmapped"
            return False
        if width <= 1 or height <= 1:
            self._last_geometry_failure_reason = (
                f"anchor size is not ready: width={width}, height={height}"
            )
            return False
        self._last_geometry_failure_reason = ""
        return True

    def sync_to_anchor(self) -> bool:
        """Apply stored placement options to the toplevel geometry."""
        return self._apply_geometry()

    def ensure_visible(self) -> bool:
        """Map the overlay when possible, retrying while its owner still exists."""
        if not self._visible or self._destroyed:
            return False
        if self.sync_to_anchor():
            try:
                self.window.deiconify()
            except tk.TclError as exc:
                self._last_geometry_failure_reason = f"overlay unavailable: {exc}"
                return False
            return True
        self._schedule_geometry_retry()
        return False

    def _cancel_geometry_retry(self) -> None:
        if self._geometry_retry_id is None:
            return
        try:
            self.master.after_cancel(self._geometry_retry_id)
        except tk.TclError:
            pass
        self._geometry_retry_id = None

    def _schedule_geometry_retry(self) -> None:
        if self._destroyed or not self._visible or self._geometry_retry_id is not None:
            return
        try:
            self._geometry_retry_id = self.master.after(50, self._run_geometry_retry)
        except tk.TclError:
            self._geometry_retry_id = None

    def _run_geometry_retry(self) -> None:
        self._geometry_retry_id = None
        self.ensure_visible()

    def _apply_geometry(self) -> bool:
        try:
            self.master.update_idletasks()
            mapped = bool(self.master.winfo_ismapped())
            width = self.master.winfo_width()
            height = self.master.winfo_height()
            if not mapped:
                self._last_geometry_failure_reason = "anchor is unmapped"
                return False
            if width <= 1 or height <= 1:
                self._last_geometry_failure_reason = (
                    f"anchor size is not ready: width={width}, height={height}"
                )
                return False
            x = self.master.winfo_rootx() + int(self._place_options.get("x") or 0)
            y = self.master.winfo_rooty() + int(self._place_options.get("y") or 0)
        except tk.TclError as exc:
            self._last_geometry_failure_reason = f"anchor unavailable: {exc}"
            return False
        self._cancel_geometry_retry()
        self.window.geometry(f"{self._width}x{height}+{x}+{y}")
        self._last_geometry_failure_reason = ""
        return True

    def lift(self) -> None:
        self.window.lift()

    def destroy(self) -> None:
        self._destroyed = True
        self._visible = False
        self._cancel_geometry_retry()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def update_idletasks(self) -> None:
        self.window.update_idletasks()
