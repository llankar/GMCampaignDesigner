"""Workspace layout tree and panel instance state for GM Screen 2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Axis = Literal["horizontal", "vertical"]


@dataclass(slots=True)
class PanelInstanceState:
    panel_id: str
    min_size: int = 220
    visible: bool = True
    collapsed: bool = False


@dataclass(slots=True)
class ZoneNode:
    id: str
    panel_stack: list[str] = field(default_factory=list)
    active_panel_id: str | None = None


@dataclass(slots=True)
class SplitNode:
    id: str
    axis: Axis
    ratio: float
    first: LayoutNode
    second: LayoutNode


LayoutNode = ZoneNode | SplitNode


@dataclass(slots=True)
class LayoutState:
    """Current workspace model with nested splits and panel visibility."""

    root: LayoutNode = field(default_factory=lambda: default_layout_tree())
    panel_instances: dict[str, PanelInstanceState] = field(default_factory=lambda: default_panel_instances())

    def reset(self) -> None:
        self.root = default_layout_tree()
        self.panel_instances = default_panel_instances()


def default_panel_instances() -> dict[str, PanelInstanceState]:
    ids = ["overview", "entities", "notes", "timeline", "quick_reference"]
    return {panel_id: PanelInstanceState(panel_id=panel_id) for panel_id in ids}


def default_layout_tree() -> LayoutNode:
    left = ZoneNode(id="zone_left", panel_stack=["overview", "entities"], active_panel_id="overview")
    middle = ZoneNode(id="zone_mid", panel_stack=["notes"], active_panel_id="notes")
    right_top = ZoneNode(id="zone_right_top", panel_stack=["timeline"], active_panel_id="timeline")
    right_bottom = ZoneNode(id="zone_right_bottom", panel_stack=["quick_reference"], active_panel_id="quick_reference")
    right = SplitNode(id="split_right", axis="vertical", ratio=0.55, first=right_top, second=right_bottom)
    return SplitNode(id="split_root", axis="horizontal", ratio=0.6, first=SplitNode(id="split_left", axis="horizontal", ratio=0.55, first=left, second=middle), second=right)
