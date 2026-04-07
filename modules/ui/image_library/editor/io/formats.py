"""Format helpers for editor export/save operations."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SUPPORTED_FILETYPES = [("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif")]


def extension_requires_rgb(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg"}


def prepare_for_export(image: Image.Image, destination: Path) -> Image.Image:
    if extension_requires_rgb(destination):
        return image.convert("RGB")
    return image
