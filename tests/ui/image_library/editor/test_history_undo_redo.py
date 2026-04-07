from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for history undo/redo tests", allow_module_level=True)

from tests.ui.image_library.editor._image_fixtures import pixel, solid_rgba

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.history.commands import AddLayerCommand, EraseCommand, StrokeCommand
from modules.ui.image_library.editor.history.history_stack import HistoryStack


def test_history_sequence_is_reversible_with_undo_and_redo() -> None:
    document = ImageDocument.from_image(solid_rgba((0, 0, 0, 0), size=(4, 4)))
    history = HistoryStack(max_depth=10)

    history.execute_command(AddLayerCommand(document, "Paint"))
    assert len(document.layers) == 2

    before_stroke = document.active_layer.copy()
    after_stroke = before_stroke.copy()
    after_stroke.putpixel((1, 1), (0, 255, 0, 255))
    history.execute_command(StrokeCommand(document, document.active_layer_index, before_stroke, after_stroke))
    assert pixel(document.active_layer, 1, 1) == (0, 255, 0, 255)

    before_erase = document.active_layer.copy()
    after_erase = before_erase.copy()
    after_erase.putpixel((1, 1), (0, 0, 0, 0))
    history.execute_command(EraseCommand(document, document.active_layer_index, before_erase, after_erase))
    assert pixel(document.active_layer, 1, 1) == (0, 0, 0, 0)

    assert history.undo() is True
    assert pixel(document.active_layer, 1, 1) == (0, 255, 0, 255)
    assert history.undo() is True
    assert pixel(document.active_layer, 1, 1) == (0, 0, 0, 0)
    assert history.undo() is True
    assert len(document.layers) == 1

    assert history.redo() is True
    assert len(document.layers) == 2
    assert history.redo() is True
    assert pixel(document.active_layer, 1, 1) == (0, 255, 0, 255)
    assert history.redo() is True
    assert pixel(document.active_layer, 1, 1) == (0, 0, 0, 0)
