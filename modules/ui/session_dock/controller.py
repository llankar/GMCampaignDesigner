"""Session dock controller that mounts/unmounts panels dynamically."""

from __future__ import annotations

from modules.ui.session_dock.core.dock_shortcuts import DockShortcutManager
from modules.ui.session_dock.core.dock_state import DockState, DockStateStore
from modules.ui.session_dock.core.dock_window import DockWindow


class SessionDockController:
    """Owns dock lifecycle and dynamic panel mounting."""

    def __init__(self, root) -> None:
        self._root = root
        self._store = DockStateStore()
        self._state = self._store.load()
        self._window = DockWindow(root, self._state, on_state_change=self._persist_state)
        self._shortcuts = DockShortcutManager(root)
        self._mounted_panels: dict[str, object] = {}
        self._next_row = 0

        self._shortcuts.bind("<Control-Alt-d>", self.toggle_visibility)
        self._shortcuts.bind("<Control-Alt-minus>", lambda: self._window.set_mode("compact"))
        self._shortcuts.bind("<Control-Alt-equal>", lambda: self._window.set_mode("full"))

        if self._state.mode == "hidden":
            self._window.hide()
        else:
            self._window.show()

    def mount_panel(self, panel_id: str, panel_cls, **kwargs):
        """Instantiate and attach a panel if not already mounted."""
        if panel_id in self._mounted_panels:
            return self._mounted_panels[panel_id]

        panel = panel_cls(self._window.container, **kwargs)
        panel.grid(row=self._next_row, column=0, sticky="ew", padx=4, pady=4)
        self._mounted_panels[panel_id] = panel
        self._next_row += 1
        return panel

    def unmount_panel(self, panel_id: str) -> bool:
        """Remove a mounted panel by id."""
        panel = self._mounted_panels.pop(panel_id, None)
        if panel is None:
            return False
        panel.destroy()
        return True

    def toggle_visibility(self) -> None:
        """Toggle hidden/full mode quickly."""
        if self._window.dock_state.mode == "hidden":
            self._window.set_mode("full")
        else:
            self._window.set_mode("hidden")

    def dispose(self) -> None:
        """Release resources and bindings."""
        self._shortcuts.clear()
        self._window.destroy()

    def _persist_state(self, state: DockState) -> None:
        self._store.save(state)
