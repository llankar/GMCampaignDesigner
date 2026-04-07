"""Layer model for the image editor."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass
class Layer:
    """Single image layer with compositing metadata."""

    name: str
    visible: bool
    opacity: float
    blend_mode: str
    image: Image.Image
