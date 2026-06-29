"""JSON-safe models for the fixed GM Table overlay."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class FixedOverlayItem:
    """One item pinned into the viewport-fixed table."""
    item_id: str
    kind: str
    title: str
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "kind": self.kind, "title": self.title, "state": dict(self.state or {})}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FixedOverlayItem":
        return cls(
            item_id=str(payload.get("item_id") or payload.get("panel_id") or ""),
            kind=str(payload.get("kind") or "note"),
            title=str(payload.get("title") or "Pinned Item"),
            state=dict(_json_dict(payload.get("state"))),
        )


@dataclass
class FixedOverlayState:
    """Viewport-fixed overlay state; no Tk objects or world coordinates."""
    visible: bool = True
    collapsed: bool = True
    width: int = 360
    anchor: str = "left"
    selected_item_ids: list[str] = field(default_factory=list)
    items: list[FixedOverlayItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "visible": bool(self.visible),
            "collapsed": bool(self.collapsed),
            "width": max(260, min(720, int(self.width or 360))),
            "anchor": self.anchor if self.anchor in {"left"} else "left",
            "selected_item_ids": [str(value) for value in self.selected_item_ids],
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "FixedOverlayState":
        source = payload if isinstance(payload, dict) else {}
        items = [FixedOverlayItem.from_dict(item) for item in list(source.get("items") or []) if isinstance(item, dict)]
        return cls(
            visible=bool(source.get("visible", True)),
            collapsed=bool(source.get("collapsed", True)),
            width=max(260, min(720, int(source.get("width") or 360))),
            anchor="left",
            selected_item_ids=[str(value) for value in list(source.get("selected_item_ids") or [])],
            items=[item for item in items if item.item_id],
        )
