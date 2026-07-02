"""Controller for fixed overlay state changes."""
from __future__ import annotations
from uuid import uuid4
from .models import FixedOverlayItem, FixedOverlayState
from .persistence import restore_state
from .view import FixedOverlayView


class FixedOverlayController:
    def __init__(self, master, *, panel_builder, on_changed=None, on_add_requested=None):
        self.view = FixedOverlayView(
            master,
            panel_builder=panel_builder,
            on_changed=on_changed,
            on_add_requested=on_add_requested,
        )
    def serialize(self) -> dict:
        return self.view.get_state()
    def restore(self, payload: dict | None) -> None:
        self.view.apply_state(restore_state(payload))
    def toggle(self) -> None:
        self.view.toggle_collapsed()
    def add_panel_item(self, kind: str, title: str, state: dict | None = None) -> str:
        item = FixedOverlayItem(item_id=f"fixed_{uuid4().hex}", kind=kind, title=title, state=dict(state or {}))
        self.view.add_item(item)
        return item.item_id
    def refresh_geometry(self) -> None:
        """Refresh the fixed overlay placement after its anchor geometry changes."""
        self.view._refresh_geometry()

    def lift(self) -> None:
        self.refresh_geometry()
        self.view.lift()
