from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for layer compositing tests", allow_module_level=True)

from modules.ui.image_library.editor.core.compositor import flatten_layers
from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.layer import Layer


def _pixel_rgba(image: Image.Image, x: int = 0, y: int = 0) -> tuple[int, int, int, int]:
    return tuple(image.getpixel((x, y)))


def test_document_starts_with_single_background_layer():
    source = Image.new("RGBA", (4, 3), (10, 20, 30, 255))

    document = ImageDocument.from_image(source)

    assert len(document.layers) == 1
    assert document.layers[0].name == "Background"
    assert document.active_layer_index == 0
    assert _pixel_rgba(document.active_layer) == (10, 20, 30, 255)


def test_layer_add_delete_move_and_visibility_controls():
    source = Image.new("RGBA", (3, 3), (0, 0, 255, 255))
    document = ImageDocument.from_image(source)

    index = document.add_layer("Ink")
    assert index == 1
    assert len(document.layers) == 2
    assert document.active_layer_index == 1

    document.active_layer.paste((255, 0, 0, 255), (0, 0, 1, 1))
    assert _pixel_rgba(document.composite()) == (255, 0, 0, 255)

    assert document.move_active_layer(-1) is True
    assert document.active_layer_index == 0
    assert _pixel_rgba(document.composite()) == (0, 0, 255, 255)

    assert document.toggle_layer_visibility(0) is True
    assert _pixel_rgba(document.composite()) == (255, 0, 0, 255)

    assert document.delete_active_layer() is True
    assert len(document.layers) == 1
    assert document.active_layer_index == 0


def test_flatten_layers_applies_layer_opacity():
    bottom = Layer(
        name="bottom",
        visible=True,
        opacity=1.0,
        blend_mode="normal",
        image=Image.new("RGBA", (1, 1), (0, 0, 255, 255)),
    )
    top = Layer(
        name="top",
        visible=True,
        opacity=0.5,
        blend_mode="normal",
        image=Image.new("RGBA", (1, 1), (255, 0, 0, 255)),
    )

    flattened = flatten_layers(1, 1, [bottom, top])

    r, g, b, a = _pixel_rgba(flattened)
    assert r > b
    assert b > 0
    assert g == 0
    assert a == 255
