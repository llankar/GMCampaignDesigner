"""Selection data model shared by editor tools and commands."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass
class SelectionModel:
    """Stores editable selection mask and related tool settings."""

    tolerance: int = 24
    feather_radius: int = 0
    mask: Image.Image | None = None
    bounds: tuple[int, int, int, int] | None = None

    def set_mask(self, mask: Image.Image | None, bounds: tuple[int, int, int, int] | None = None) -> None:
        if mask is None:
            self.clear()
            return
        self.mask = mask.convert("L")
        self.bounds = bounds or self.mask.getbbox()

    def has_selection(self) -> bool:
        return self.mask is not None and self.mask.getbbox() is not None

    def clear(self) -> None:
        self.mask = None
        self.bounds = None
