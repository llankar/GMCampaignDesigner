from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for editor dialog tests", allow_module_level=True)

try:
    from PIL import ImageEnhance  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageEnhance support is required for editor dialog tests", allow_module_level=True)

from modules.ui.image_library.editor.image_editor_dialog import ImageEditorDialog
from modules.ui.image_library.editor.core.layer import Layer


class _DocumentStub:
    def __init__(self) -> None:
        self.calls = 0

    def composite(self) -> Image.Image:
        self.calls += 1
        return Image.new("RGBA", (8, 8), (0, 0, 0, 0))


class _HistoryStub:
    def execute_command(self, _command) -> None:
        return


class _LayersPanelStub:
    def refresh(self) -> None:
        return


def test_drag_refresh_is_throttled_with_after_coalescing() -> None:
    dialog = ImageEditorDialog.__new__(ImageEditorDialog)
    dialog._drag_needs_render = False
    dialog._drag_in_progress = True
    dialog._drag_render_after_id = None

    after_calls: list[int] = []
    scheduled_callbacks = []
    refresh_calls = {"count": 0}

    def _after(ms: int, callback):
        after_calls.append(ms)
        scheduled_callbacks.append(callback)
        return "after-id"

    dialog.after = _after
    dialog._refresh_preview_fast = lambda: refresh_calls.__setitem__("count", refresh_calls["count"] + 1)

    dialog._schedule_drag_refresh()
    dialog._schedule_drag_refresh()
    dialog._schedule_drag_refresh()

    assert after_calls == [16]
    assert len(scheduled_callbacks) == 1

    scheduled_callbacks[0]()
    assert refresh_calls["count"] == 1


def test_flattened_cache_invalidates_on_execute_command() -> None:
    dialog = ImageEditorDialog.__new__(ImageEditorDialog)
    dialog._document = _DocumentStub()
    dialog._flattened_cache = None
    dialog._flattened_cache_valid = False
    dialog._drag_flattened_without_active = None

    assert dialog._get_flattened_image() is not None
    assert dialog._get_flattened_image() is not None
    assert dialog._document.calls == 1

    dialog._history = _HistoryStub()
    dialog._layers_panel = _LayersPanelStub()
    dialog._refresh_preview = lambda: None
    dialog._update_history_buttons = lambda: None

    dialog.execute_command(object())

    assert dialog._flattened_cache is None
    assert dialog._flattened_cache_valid is False
    assert dialog._get_flattened_image() is not None
    assert dialog._document.calls == 2


def test_drag_preview_respects_layer_stack_order() -> None:
    dialog = ImageEditorDialog.__new__(ImageEditorDialog)
    dialog._apply_preview_adjustments = lambda image: image

    bottom = Layer(
        name="Bottom ink",
        visible=True,
        opacity=1.0,
        blend_mode="normal",
        image=Image.new("RGBA", (1, 1), (255, 0, 0, 255)),
    )
    top = Layer(
        name="Top cover",
        visible=True,
        opacity=1.0,
        blend_mode="normal",
        image=Image.new("RGBA", (1, 1), (0, 0, 255, 255)),
    )
    dialog._document = type("Doc", (), {"width": 1, "height": 1, "layers": [bottom, top], "active_layer_index": 0})()

    preview = dialog._build_drag_preview_image()

    assert preview is not None
    assert preview.getpixel((0, 0)) == (0, 0, 255, 255)
