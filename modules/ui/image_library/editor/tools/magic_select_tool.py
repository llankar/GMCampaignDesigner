"""Magic select tool using flood-fill and selection tolerance."""

from __future__ import annotations

from modules.ui.image_library.editor.selection.magic_wand import magic_select_mask
from modules.ui.image_library.editor.selection.selection_model import SelectionModel


class MagicSelectTool:
    def __init__(self, image_getter, selection: SelectionModel) -> None:
        self._image_getter = image_getter
        self._selection = selection

    def on_press(self, x: float, y: float) -> None:
        image = self._image_getter()
        if image is None:
            self._selection.clear()
            return
        mask = magic_select_mask(image, int(x), int(y), tolerance=int(self._selection.tolerance))
        self._selection.set_mask(mask)

    def on_drag(self, _x: float, _y: float) -> None:
        return

    def on_release(self, _x: float, _y: float) -> None:
        return
