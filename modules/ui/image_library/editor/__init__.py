"""Image editor package for image-library workflows."""

from __future__ import annotations

from typing import Any

__all__ = ["ImageEditorDialog"]


def __getattr__(name: str) -> Any:
    if name == "ImageEditorDialog":
        from modules.ui.image_library.editor.image_editor_dialog import ImageEditorDialog

        return ImageEditorDialog
    raise AttributeError(name)
