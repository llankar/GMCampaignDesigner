"""Rectangle selection tool."""

from __future__ import annotations

from PIL import Image, ImageDraw

from modules.ui.image_library.editor.selection.selection_model import SelectionModel


class RectSelectTool:
    def __init__(self, selection: SelectionModel, canvas_size_getter) -> None:
        self._selection = selection
        self._canvas_size_getter = canvas_size_getter
        self._start: tuple[int, int] | None = None
        self._current: tuple[int, int] | None = None

    def on_press(self, x: float, y: float) -> None:
        self._start = (int(x), int(y))
        self._current = (int(x), int(y))

    def on_drag(self, x: float, y: float) -> None:
        if self._start is None:
            return
        self._current = (int(x), int(y))

    def on_release(self, x: float, y: float) -> None:
        if self._start is None:
            return
        self._current = (int(x), int(y))
        self._apply_selection()
        self._start = None
        self._current = None

    def _apply_selection(self) -> None:
        width, height = self._canvas_size_getter()
        if self._start is None or self._current is None:
            self._selection.clear()
            return
        x0, y0 = self._start
        x1, y1 = self._current
        left, right = sorted((max(0, x0), min(width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(height - 1, y1)))
        if right <= left or bottom <= top:
            self._selection.clear()
            return

        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle((left, top, right, bottom), fill=255)
        self._selection.set_mask(mask, bounds=(left, top, right + 1, bottom + 1))
