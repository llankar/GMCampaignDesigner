"""Split-handle helpers for workspace compositor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SplitHandleBinding:
    split_id: str
    axis: str
