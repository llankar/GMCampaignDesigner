"""Eraser tool for non-destructive alpha clearing."""

from __future__ import annotations

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.render.stroke_renderer import StrokeRenderer


class EraserTool:
    """Eraser tool with press/drag/release stroke lifecycle."""

    def __init__(self, document: ImageDocument, renderer: StrokeRenderer, *, size_getter, opacity_getter, hardness_getter) -> None:
        self._document = document
        self._renderer = renderer
        self._size_getter = size_getter
        self._opacity_getter = opacity_getter
        self._hardness_getter = hardness_getter
        self._last_point: tuple[float, float] | None = None

    def on_press(self, x: float, y: float) -> None:
        self._last_point = (x, y)
        self._stroke((x, y), (x, y))

    def on_drag(self, x: float, y: float) -> None:
        if self._last_point is None:
            self.on_press(x, y)
            return
        point = (x, y)
        self._stroke(self._last_point, point)
        self._last_point = point

    def on_release(self, x: float, y: float) -> None:
        if self._last_point is not None:
            self._stroke(self._last_point, (x, y))
        self._last_point = None

    def _stroke(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        self._renderer.render_stroke(
            self._document.active_layer,
            start,
            end,
            size=float(self._size_getter()),
            opacity=float(self._opacity_getter()),
            hardness=float(self._hardness_getter()),
            color=(0, 0, 0, 0),
            erase=True,
        )
