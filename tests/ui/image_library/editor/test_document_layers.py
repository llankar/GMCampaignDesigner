from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for document layer tests", allow_module_level=True)

from tests.ui.image_library.editor._image_fixtures import pixel, solid_rgba

from modules.ui.image_library.editor.core.document import ImageDocument


def test_document_layer_add_remove_reorder_visibility() -> None:
    document = ImageDocument.from_image(solid_rgba((0, 0, 255, 255), size=(4, 4)))

    top_index = document.add_layer("Ink")
    assert top_index == 1

    document.active_layer.putpixel((1, 1), (255, 0, 0, 255))
    assert pixel(document.composite(), 1, 1) == (255, 0, 0, 255)

    assert document.move_active_layer(-1) is True
    assert document.active_layer_index == 0
    assert pixel(document.composite(), 1, 1) == (0, 0, 255, 255)

    assert document.toggle_layer_visibility(0) is True
    assert pixel(document.composite(), 1, 1) == (255, 0, 0, 255)

    assert document.delete_active_layer() is True
    assert len(document.layers) == 1
    assert document.active_layer_index == 0
