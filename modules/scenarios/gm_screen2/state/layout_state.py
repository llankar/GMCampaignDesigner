"""Mutable layout state for GM Screen 2 desktop mode."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LayoutState:
    """Current panel arrangement and tab visibility."""

    split_ratios: list[float] = field(default_factory=lambda: [0.34, 0.33, 0.33])
    panel_order: list[str] = field(
        default_factory=lambda: ["overview", "entities", "notes", "timeline", "quick_reference"]
    )
    active_tabs: dict[str, str] = field(default_factory=dict)
    hidden_panels: set[str] = field(default_factory=set)

    def set_split_ratios(self, ratios: list[float]) -> None:
        """Replace split ratios while keeping values bounded."""
        bounded = [max(0.1, min(0.8, value)) for value in ratios]
        self.split_ratios = bounded

    def set_panel_hidden(self, panel_id: str, hidden: bool) -> None:
        """Toggle panel visibility."""
        if hidden:
            self.hidden_panels.add(panel_id)
        else:
            self.hidden_panels.discard(panel_id)
