"""Optional selection-move tool for future move workflows."""

from __future__ import annotations

from PIL import ImageChops

from modules.ui.image_library.editor.selection.selection_model import SelectionModel


class MoveSelectionTool:
    def __init__(self, selection: SelectionModel) -> None:
        self._selection = selection
        self._anchor: tuple[int, int] | None = None

    def on_press(self, x: float, y: float) -> None:
        self._anchor = (int(x), int(y))

    def on_drag(self, x: float, y: float) -> None:
        if self._anchor is None or self._selection.mask is None:
            return
        dx = int(x) - self._anchor[0]
        dy = int(y) - self._anchor[1]
        shifted = ImageChops.offset(self._selection.mask, dx, dy)
        self._selection.set_mask(shifted)
        self._anchor = (int(x), int(y))

    def on_release(self, _x: float, _y: float) -> None:
        self._anchor = None
