from __future__ import annotations

from dataclasses import dataclass

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for editor dialog tests", allow_module_level=True)

try:
    from PIL import ImageEnhance  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageEnhance support is required for editor dialog tests", allow_module_level=True)

from tests.ui.image_library.editor._image_fixtures import pixel, solid_rgba

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.render.stroke_renderer import StrokeRenderer
from modules.ui.image_library.editor.history.history_stack import HistoryStack
from modules.ui.image_library.editor.image_editor_dialog import ImageEditorDialog
from modules.ui.image_library.editor.tools import BrushTool, EraserTool


class _VarStub:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class _LayersPanelStub:
    def __init__(self) -> None:
        self.synced_index: int | None = None

    def sync_active_layer(self, index: int) -> None:
        self.synced_index = index

    def refresh(self) -> None:
        return


@dataclass
class _EventStub:
    x: int = 2
    y: int = 2


def _build_dialog(document: ImageDocument) -> ImageEditorDialog:
    dialog = ImageEditorDialog.__new__(ImageEditorDialog)
    dialog._document = document
    dialog._history = HistoryStack(max_depth=20)
    dialog._layers_panel = _LayersPanelStub()
    dialog._renderer = StrokeRenderer()
    dialog._brush_size_var = _VarStub(2.0)
    dialog._brush_opacity_var = _VarStub(1.0)
    dialog._active_tool_var = _VarStub("Paint")
    dialog._brush_tool = BrushTool(
        document,
        dialog._renderer,
        size_getter=dialog._brush_size_var.get,
        opacity_getter=dialog._brush_opacity_var.get,
        hardness_getter=lambda: 1.0,
        color=(255, 0, 0, 255),
    )
    dialog._eraser_tool = EraserTool(
        document,
        dialog._renderer,
        size_getter=dialog._brush_size_var.get,
        opacity_getter=dialog._brush_opacity_var.get,
        hardness_getter=lambda: 1.0,
    )
    dialog._canvas_to_document = lambda _x, _y: (2.0, 2.0)
    dialog._refresh_preview_fast = lambda: None
    dialog._invalidate_preview_caches = lambda: None
    dialog._refresh_preview = lambda: None
    dialog._update_history_buttons = lambda: None
    dialog.execute_command = lambda command: dialog._history.execute_command(command)
    dialog._drag_in_progress = False
    dialog._drag_needs_render = False
    dialog._drag_render_after_id = None
    dialog._drag_flattened_without_active = None
    dialog._stroke_before = None
    dialog._stroke_layer_index = None
    return dialog


def test_add_layer_then_paint_modifies_only_new_layer() -> None:
    document = ImageDocument.from_image(solid_rgba((0, 0, 0, 0), size=(6, 6)))
    dialog = _build_dialog(document)

    assert dialog._add_layer() is True
    assert document.active_layer_index == 1
    assert dialog._layers_panel.synced_index == 1

    dialog._on_canvas_press(_EventStub())
    dialog._on_canvas_release(_EventStub())

    assert pixel(document.layers[1].image, 2, 2) == (255, 0, 0, 255)
    assert pixel(document.layers[0].image, 2, 2) == (0, 0, 0, 0)


def test_add_layer_then_eraser_affects_only_new_layer_alpha() -> None:
    document = ImageDocument.from_image(solid_rgba((10, 20, 30, 255), size=(6, 6)))
    dialog = _build_dialog(document)

    dialog._add_layer()
    document.layers[1].image.putpixel((2, 2), (200, 100, 50, 255))
    dialog._active_tool_var = _VarStub("Eraser")

    dialog._on_canvas_press(_EventStub())
    dialog._on_canvas_release(_EventStub())

    assert pixel(document.layers[1].image, 2, 2)[3] == 0
    assert pixel(document.layers[0].image, 2, 2)[3] == 255


def test_switching_layers_between_strokes_keeps_history_consistent() -> None:
    document = ImageDocument.from_image(solid_rgba((0, 0, 0, 0), size=(6, 6)))
    dialog = _build_dialog(document)
    dialog._add_layer()

    dialog._on_canvas_press(_EventStub())
    dialog._on_canvas_release(_EventStub())

    dialog._sync_active_layer_ui(0)
    dialog._on_layers_changed()

    dialog._on_canvas_press(_EventStub())
    dialog._on_canvas_release(_EventStub())

    assert pixel(document.layers[0].image, 2, 2) == (255, 0, 0, 255)
    assert pixel(document.layers[1].image, 2, 2) == (255, 0, 0, 255)

    assert dialog._history.undo() is True
    assert pixel(document.layers[0].image, 2, 2) == (0, 0, 0, 0)
    assert pixel(document.layers[1].image, 2, 2) == (255, 0, 0, 255)

    assert dialog._history.undo() is True
    assert pixel(document.layers[0].image, 2, 2) == (0, 0, 0, 0)
    assert pixel(document.layers[1].image, 2, 2) == (0, 0, 0, 0)
