from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class TourPlacement(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


TourHook = Callable[["TourStep"], None]


@dataclass(frozen=True)
class TourStep:
    id: str
    screen: str
    target_widget_key: str
    title: str
    description: str
    placement: TourPlacement = TourPlacement.BOTTOM
    before_hook: Optional[TourHook] = None
    after_hook: Optional[TourHook] = None
