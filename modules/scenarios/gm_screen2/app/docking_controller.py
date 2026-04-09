"""Docking controller that mutates layout state in response to commands."""

from __future__ import annotations

from modules.scenarios.gm_screen2.events.contracts import EventBus
from modules.scenarios.gm_screen2.state.layout_reducer import merge_zone, move_panel, resize_split, split_zone, toggle_visibility
from modules.scenarios.gm_screen2.state.layout_serializer import deserialize_layout, serialize_layout
from modules.scenarios.gm_screen2.state.layout_state import LayoutState


class DockingController:
    """Command handler for workspace docking actions."""

    def __init__(self, layout: LayoutState, events: EventBus) -> None:
        self._layout = layout
        self._events = events

    def move_panel(self, panel_id: str, target_zone_id: str, index: int | None = None) -> None:
        move_panel(self._layout, panel_id, target_zone_id, index)
        self._publish("move_panel")

    def split_zone(self, zone_id: str, axis: str, new_zone_id: str, moved_panel_id: str | None = None) -> None:
        split_zone(self._layout, zone_id, axis, new_zone_id, moved_panel_id)
        self._publish("split_zone")

    def merge_zone(self, zone_id: str, into_zone_id: str) -> None:
        merge_zone(self._layout, zone_id, into_zone_id)
        self._publish("merge_zone")

    def toggle_visibility(self, panel_id: str) -> None:
        toggle_visibility(self._layout, panel_id)
        self._publish("toggle_visibility")

    def resize_split(self, split_id: str, ratio: float) -> None:
        resize_split(self._layout, split_id, ratio)
        self._publish("resize_split")

    def reset_layout(self) -> None:
        self._layout.reset()
        self._publish("reset_layout")

    def export_layout(self) -> dict[str, object]:
        return serialize_layout(self._layout)

    def import_layout(self, data: dict[str, object]) -> None:
        loaded = deserialize_layout(data)
        self._layout.root = loaded.root
        self._layout.panel_instances = loaded.panel_instances
        self._publish("import_layout")

    def _publish(self, action: str) -> None:
        self._events.publish("layout_changed", {"action": action})
        self._events.publish("state_changed", {"action": action})
