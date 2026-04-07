"""Persistence service for image-editor save/export flows."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from modules.ui.image_library.editor.io.formats import prepare_for_export


class SaveService:
    """Centralized image persistence for editor document exports."""

    def save_image(self, image: Image.Image, target_path: str) -> Path:
        destination = Path(target_path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        image_to_save = prepare_for_export(image, destination)
        image_to_save.save(destination)
        return destination
