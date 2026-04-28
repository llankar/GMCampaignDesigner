"""Top-level dock window for mounting session panels."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from modules.ui.session_dock.core.dock_state import DockMode, DockState


class DockWindow(ctk.CTkToplevel):
    """Dedicated floating window with pinning and display modes."""

    def __init__(
        self,
        master: ctk.CTk,
        state: DockState,
        on_state_change: Callable[[DockState], None],
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("Session Dock")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self._master = master
        self._state = state
        self._on_state_change = on_state_change

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=8, pady=8)

        self.protocol("WM_DELETE_WINDOW", self.hide)
        self._parent_configure_bind_id = master.bind(
            "<Configure>",
            self._on_parent_configure,
            add="+",
        )

        self._apply_state_geometry()

    @property
    def dock_state(self) -> DockState:
        """Return persisted dock state without shadowing Tk's ``state()`` API."""
        return self._state

    def show(self) -> None:
        """Show and raise the dock."""
        self._state.mode = "full" if self._state.mode == "hidden" else self._state.mode
        self.deiconify()
        self.lift()
        self._apply_state_geometry()
        self._notify()

    def hide(self) -> None:
        """Hide the dock and persist hidden state."""
        self.withdraw()
        self._state.mode = "hidden"
        self._notify()

    def set_mode(self, mode: DockMode) -> None:
        """Switch between hidden, compact and full layouts."""
        self._state.mode = mode
        if mode == "hidden":
            self.withdraw()
        else:
            self.deiconify()
            self._apply_state_geometry()
        self._notify()

    def pin_to_edge(self, edge: str) -> None:
        """Pin dock window to one edge of the main window."""
        self._state.pinned_edge = edge  # type: ignore[assignment]
        if self._state.mode != "hidden":
            self._apply_state_geometry()
        self._notify()

    def set_opacity(self, opacity: float) -> None:
        """Apply opacity and persist value."""
        normalized = max(0.35, min(1.0, float(opacity)))
        self._state.opacity = normalized
        self.attributes("-alpha", normalized)
        self._notify()

    def _notify(self) -> None:
        self._on_state_change(self._state)

    def _on_parent_configure(self, _event=None) -> None:
        if self._state.mode != "hidden":
            self._apply_state_geometry()

    def _apply_state_geometry(self) -> None:
        self.attributes("-alpha", self._state.opacity)
        self.update_idletasks()

        master_x = self._master.winfo_rootx()
        master_y = self._master.winfo_rooty()
        master_w = self._master.winfo_width()
        master_h = self._master.winfo_height()

        width = 320 if self._state.mode == "full" else 220
        base_height = 400 if self._state.mode == "full" else 240
        content_height = self.container.winfo_reqheight() + 16
        max_height = max(220, master_h - 24)
        height = max(base_height, min(content_height, max_height))

        if self._state.pinned_edge == "left":
            x, y = master_x, master_y + 64
        elif self._state.pinned_edge == "top":
            x, y = master_x + 64, master_y
        elif self._state.pinned_edge == "bottom":
            x, y = master_x + 64, master_y + max(0, master_h - height)
        else:
            x, y = master_x + max(0, master_w - width), master_y + 64

        self.geometry(f"{width}x{height}+{x}+{y}")

    def destroy(self) -> None:
        """Unbind parent listeners before destroying the dock window."""
        if self._parent_configure_bind_id is not None:
            self._master.unbind("<Configure>", self._parent_configure_bind_id)
            self._parent_configure_bind_id = None
        super().destroy()
