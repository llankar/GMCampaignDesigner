from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for editor selection tests", allow_module_level=True)

try:
    from PIL import ImageEnhance  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageEnhance support is required for editor selection tests", allow_module_level=True)

from modules.ui.image_library.editor.selection.magic_wand import magic_select_mask


def test_magic_select_tolerance_expands_with_higher_threshold() -> None:
    image = Image.new("RGBA", (3, 1), (0, 0, 0, 255))
    image.putpixel((1, 0), (5, 5, 5, 255))
    image.putpixel((2, 0), (80, 80, 80, 255))

    strict = magic_select_mask(image, 0, 0, tolerance=0)
    relaxed = magic_select_mask(image, 0, 0, tolerance=10)

    assert strict.getbbox() == (0, 0, 1, 1)
    assert relaxed.getbbox() == (0, 0, 2, 1)
    assert relaxed.getpixel((2, 0)) == 0
