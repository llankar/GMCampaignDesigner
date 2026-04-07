"""Shape tool for rectangle and ellipse drawing."""

from __future__ import annotations

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.render.stroke_renderer import StrokeRenderer


class ShapeTool:
    """Draws rectangle/ellipse outlines with paint.net-style drag interactions."""

    def __init__(
        self,
        document: ImageDocument,
        renderer: StrokeRenderer,
        *,
        color_getter,
        opacity_getter,
        stroke_width_getter,
        shape: str,
    ) -> None:
        self._document = document
        self._renderer = renderer
        self._color_getter = color_getter
        self._opacity_getter = opacity_getter
        self._stroke_width_getter = stroke_width_getter
        self._shape = shape
        self._start_point: tuple[float, float] | None = None
        self._base_layer = None
        self._constrain_proportions = False

    def set_constrain_proportions(self, enabled: bool) -> None:
        self._constrain_proportions = bool(enabled)

    def on_press(self, x: float, y: float) -> None:
        self._start_point = (x, y)
        self._base_layer = self._document.active_layer.copy()
        self._render_preview((x, y))

    def on_drag(self, x: float, y: float) -> None:
        if self._start_point is None:
            self.on_press(x, y)
            return
        self._render_preview((x, y))

    def on_release(self, x: float, y: float) -> None:
        if self._start_point is None:
            return
        self._render_preview((x, y))
        self._start_point = None
        self._base_layer = None

    def _render_preview(self, current: tuple[float, float]) -> None:
        if self._start_point is None:
            return
        base = self._base_layer.copy() if self._base_layer is not None else self._document.active_layer.copy()
        self._document.active_layer.paste(base)
        self._renderer.render_shape(
            self._document.active_layer,
            self._start_point,
            current,
            shape=self._shape,
            color=self._color_getter(),
            opacity=float(self._opacity_getter()),
            stroke_width=float(self._stroke_width_getter()),
            constrain_proportions=self._constrain_proportions,
        )
