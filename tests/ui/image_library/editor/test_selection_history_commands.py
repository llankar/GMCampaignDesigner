from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for editor selection history tests", allow_module_level=True)

try:
    from PIL import ImageEnhance  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageEnhance support is required for editor selection history tests", allow_module_level=True)

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.history.commands import CutSelectionCommand, PasteSelectionCommand
from modules.ui.image_library.editor.selection.clipboard import SelectionClipboard


def test_cut_and_paste_selection_are_reversible() -> None:
    document = ImageDocument.from_image(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
    document.active_layer.putpixel((1, 1), (255, 0, 0, 255))

    mask = Image.new("L", (4, 4), 0)
    mask.putpixel((1, 1), 255)

    clipboard = SelectionClipboard()

    cut_command = CutSelectionCommand(document, 0, mask, clipboard)
    cut_command.execute()
    assert document.active_layer.getpixel((1, 1)) == (0, 0, 0, 0)
    assert clipboard.has_data() is True

    cut_command.undo()
    assert document.active_layer.getpixel((1, 1)) == (255, 0, 0, 255)

    cut_command.execute()
    paste_command = PasteSelectionCommand(document, 0, clipboard)
    paste_command.execute()
    assert document.active_layer.getpixel((1, 1)) == (255, 0, 0, 255)

    paste_command.undo()
    assert document.active_layer.getpixel((1, 1)) == (0, 0, 0, 0)
