from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for brush/eraser tool tests", allow_module_level=True)

try:
    from PIL import ImageChops  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageChops support is required for brush/eraser tool tests", allow_module_level=True)

from tests.ui.image_library.editor._image_fixtures import pixel, solid_rgba

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.render.stroke_renderer import StrokeRenderer
from modules.ui.image_library.editor.core.tools.brush_tool import BrushTool
from modules.ui.image_library.editor.core.tools.eraser_tool import EraserTool


def test_brush_stroke_paints_active_layer_pixels() -> None:
    document = ImageDocument.from_image(solid_rgba((0, 0, 0, 0)))
    tool = BrushTool(
        document,
        StrokeRenderer(),
        size_getter=lambda: 2.0,
        opacity_getter=lambda: 1.0,
        hardness_getter=lambda: 1.0,
        color=(255, 0, 0, 255),
    )

    tool.on_press(2, 2)
    tool.on_release(2, 2)

    assert pixel(document.active_layer, 2, 2) == (255, 0, 0, 255)
    assert pixel(document.active_layer, 0, 0) == (0, 0, 0, 0)


def test_eraser_clears_alpha_on_active_layer() -> None:
    document = ImageDocument.from_image(solid_rgba((255, 0, 0, 255)))
    tool = EraserTool(
        document,
        StrokeRenderer(),
        size_getter=lambda: 2.0,
        opacity_getter=lambda: 1.0,
        hardness_getter=lambda: 1.0,
    )

    tool.on_press(3, 3)
    tool.on_release(3, 3)

    assert pixel(document.active_layer, 3, 3)[3] == 0
    assert pixel(document.active_layer, 0, 0) == (255, 0, 0, 255)
