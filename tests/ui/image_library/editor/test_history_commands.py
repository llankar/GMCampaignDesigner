from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for history command tests", allow_module_level=True)

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.history.commands import (
    AddLayerCommand,
    BrightnessCommand,
    ContrastCommand,
    DeleteLayerCommand,
    EraseCommand,
    FlipCommand,
    MoveLayerCommand,
    RotateCommand,
    StrokeCommand,
    ToggleLayerVisibilityCommand,
)


def _pixel(image: Image.Image, x: int = 0, y: int = 0) -> tuple[int, int, int, int]:
    return tuple(image.getpixel((x, y)))


def test_stroke_and_erase_commands_are_reversible() -> None:
    document = ImageDocument.from_image(Image.new("RGBA", (2, 2), (0, 0, 0, 0)))
    before = document.active_layer.copy()

    painted = before.copy()
    painted.putpixel((0, 0), (255, 0, 0, 255))

    stroke = StrokeCommand(document, 0, before, painted)
    stroke.execute()
    assert _pixel(document.active_layer) == (255, 0, 0, 255)

    stroke.undo()
    assert _pixel(document.active_layer) == (0, 0, 0, 0)

    erased = painted.copy()
    erased.putpixel((0, 0), (0, 0, 0, 0))
    erase = EraseCommand(document, 0, painted, erased)
    erase.execute()
    assert _pixel(document.active_layer) == (0, 0, 0, 0)

    erase.undo()
    assert _pixel(document.active_layer) == (255, 0, 0, 255)


def test_transform_and_layer_commands_restore_previous_state() -> None:
    source = Image.new("RGBA", (2, 3), (10, 20, 30, 255))
    source.putpixel((1, 2), (200, 20, 30, 255))
    document = ImageDocument.from_image(source)

    rotate = RotateCommand(document, 90)
    rotate.execute()
    assert (document.width, document.height) == (3, 2)
    rotate.undo()
    assert (document.width, document.height) == (2, 3)

    flip = FlipCommand(document, horizontal=True)
    before_left = tuple(document.active_layer.getpixel((0, 0)))
    before_right = tuple(document.active_layer.getpixel((1, 0)))
    flip.execute()
    assert tuple(document.active_layer.getpixel((0, 0))) == before_right
    flip.undo()
    assert tuple(document.active_layer.getpixel((0, 0))) == before_left

    add = AddLayerCommand(document)
    add.execute()
    assert len(document.layers) == 2
    add.undo()
    assert len(document.layers) == 1

    add.execute()
    move = MoveLayerCommand(document, -1)
    move.execute()
    assert document.active_layer_index == 0
    move.undo()
    assert document.active_layer_index == 1

    toggle = ToggleLayerVisibilityCommand(document)
    visible_before = document.layers[document.active_layer_index].visible
    toggle.execute()
    assert document.layers[document.active_layer_index].visible is (not visible_before)
    toggle.undo()
    assert document.layers[document.active_layer_index].visible is visible_before

    delete = DeleteLayerCommand(document)
    delete.execute()
    assert len(document.layers) == 1
    delete.undo()
    assert len(document.layers) == 2


def test_brightness_and_contrast_commands_are_reversible() -> None:
    state = {"brightness": 1.0, "contrast": 1.0}

    brightness = BrightnessCommand(1.0, 1.4, setter=lambda value: state.__setitem__("brightness", value))
    brightness.execute()
    assert state["brightness"] == 1.4
    brightness.undo()
    assert state["brightness"] == 1.0

    contrast = ContrastCommand(1.0, 0.8, setter=lambda value: state.__setitem__("contrast", value))
    contrast.execute()
    assert state["contrast"] == 0.8
    contrast.undo()
    assert state["contrast"] == 1.0
