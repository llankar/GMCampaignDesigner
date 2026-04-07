from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for editor layer panel tests", allow_module_level=True)

try:
    from PIL import ImageEnhance  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageEnhance support is required for editor layer panel tests", allow_module_level=True)

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.widgets.layers_panel import LayersPanel


class _ListboxStub:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.selected: tuple[int, ...] = ()
        self.activated: int | None = None

    def delete(self, _start, _end) -> None:
        self.items.clear()

    def insert(self, _end, value: str) -> None:
        self.items.append(value)

    def selection_clear(self, _start, _end) -> None:
        self.selected = ()

    def selection_set(self, index: int) -> None:
        self.selected = (index,)

    def activate(self, index: int) -> None:
        self.activated = index

    def curselection(self) -> tuple[int, ...]:
        return self.selected


class _EventStub:
    pass


def _build_panel(document: ImageDocument) -> LayersPanel:
    panel = LayersPanel.__new__(LayersPanel)
    panel._document = document
    panel._listbox = _ListboxStub()
    panel._on_changed = lambda: None
    panel._on_add = None
    panel._on_delete = None
    panel._on_move = None
    panel._on_toggle_visibility = None
    return panel


def test_layers_panel_displays_topmost_layer_first() -> None:
    document = ImageDocument.from_image(Image.new("RGBA", (2, 2), (0, 0, 0, 0)))
    document.add_layer("Mid")
    document.add_layer("Top")
    panel = _build_panel(document)

    panel.refresh()

    assert panel._listbox.items[0].endswith("Top")
    assert panel._listbox.items[1].endswith("Mid")
    assert panel._listbox.items[2].endswith("Background")


def test_layers_panel_selection_maps_display_index_to_layer_index() -> None:
    document = ImageDocument.from_image(Image.new("RGBA", (2, 2), (0, 0, 0, 0)))
    document.add_layer("Top")
    panel = _build_panel(document)
    panel.refresh()

    panel._listbox.selection_set(0)
    panel._on_select(_EventStub())

    assert document.active_layer_index == 1
