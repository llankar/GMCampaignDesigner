from __future__ import annotations

from PIL import Image
import pytest

if not hasattr(Image, "new"):
    pytest.skip("Pillow runtime is required for editor dialog tests", allow_module_level=True)

try:
    from PIL import ImageEnhance  # noqa: F401
except ImportError:  # pragma: no cover - runtime capability guard
    pytest.skip("Pillow ImageEnhance support is required for editor dialog tests", allow_module_level=True)

from tests.ui.image_library.editor._image_fixtures import solid_rgba

from modules.ui.image_library.browser_panel import ImageBrowserPanel
from modules.ui.image_library.editor.image_editor_dialog import ImageEditorDialog
from modules.ui.image_library.editor.windowing import apply_startup_window_mode
from modules.ui.image_library.result_card import ImageResult


class _VarStub:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value



def test_editor_tool_switch_uses_active_tool_var() -> None:
    dialog = ImageEditorDialog.__new__(ImageEditorDialog)
    dialog._brush_tool = object()
    dialog._eraser_tool = object()
    dialog._active_tool_var = _VarStub("Paint")

    assert dialog._get_active_tool() is dialog._brush_tool

    dialog._active_tool_var = _VarStub("Eraser")
    assert dialog._get_active_tool() is dialog._eraser_tool


def test_editor_keyboard_shortcuts_are_bound(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    solid_rgba((12, 34, 56, 255), size=(2, 2)).save(image_path)

    bind_calls: list[str] = []

    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.ctk.CTkToplevel.__init__", lambda self, _master: None)
    monkeypatch.setattr(ImageEditorDialog, "title", lambda self, _value: None)
    monkeypatch.setattr(ImageEditorDialog, "geometry", lambda self, _value: None)
    monkeypatch.setattr(ImageEditorDialog, "minsize", lambda self, _w, _h: None)
    transient_calls = {"count": 0}
    monkeypatch.setattr(ImageEditorDialog, "transient", lambda self, _master: transient_calls.__setitem__("count", transient_calls["count"] + 1))
    monkeypatch.setattr(ImageEditorDialog, "grab_set", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "grid_rowconfigure", lambda self, _row, weight=0: None)
    monkeypatch.setattr(ImageEditorDialog, "grid_columnconfigure", lambda self, _col, weight=0: None)
    monkeypatch.setattr(ImageEditorDialog, "lift", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "focus_force", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "state", lambda self, _value: None)
    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.apply_startup_window_mode", lambda _window: None)
    monkeypatch.setattr(ImageEditorDialog, "_build_layout", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "_load_image", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "bind", lambda self, sequence, callback: bind_calls.append(sequence))

    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.tk.DoubleVar", lambda value=0.0: _VarStub(value))
    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.tk.StringVar", lambda value="": _VarStub(value))

    ImageEditorDialog(master=None, image_path=str(image_path))

    assert {
        "<Escape>",
        "<Control-z>",
        "<Control-y>",
        "<Control-Shift-Z>",
        "<Control-Shift-z>",
        "<F11>",
    }.issubset(set(bind_calls))
    assert transient_calls["count"] == 0


def test_editor_windowing_flags_are_configurable(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    solid_rgba((12, 34, 56, 255), size=(2, 2)).save(image_path)

    transient_calls = {"count": 0}
    grab_calls = {"count": 0}
    startup_calls = {"count": 0}

    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.ctk.CTkToplevel.__init__", lambda self, _master: None)
    monkeypatch.setattr(ImageEditorDialog, "title", lambda self, _value: None)
    monkeypatch.setattr(ImageEditorDialog, "geometry", lambda self, _value=None: "1120x760" if _value is None else None)
    monkeypatch.setattr(ImageEditorDialog, "minsize", lambda self, _w, _h: None)
    monkeypatch.setattr(ImageEditorDialog, "transient", lambda self, _master: transient_calls.__setitem__("count", transient_calls["count"] + 1))
    monkeypatch.setattr(ImageEditorDialog, "grab_set", lambda self: grab_calls.__setitem__("count", grab_calls["count"] + 1))
    monkeypatch.setattr(ImageEditorDialog, "grid_rowconfigure", lambda self, _row, weight=0: None)
    monkeypatch.setattr(ImageEditorDialog, "grid_columnconfigure", lambda self, _col, weight=0: None)
    monkeypatch.setattr(ImageEditorDialog, "lift", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "focus_force", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "_build_layout", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "_load_image", lambda self: None)
    monkeypatch.setattr(ImageEditorDialog, "bind", lambda self, _sequence, _callback: None)
    monkeypatch.setattr(
        "modules.ui.image_library.editor.image_editor_dialog.apply_startup_window_mode",
        lambda _window: startup_calls.__setitem__("count", startup_calls["count"] + 1),
    )
    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.tk.DoubleVar", lambda value=0.0: _VarStub(value))
    monkeypatch.setattr("modules.ui.image_library.editor.image_editor_dialog.tk.StringVar", lambda value="": _VarStub(value))

    master = object()
    ImageEditorDialog(master=master, image_path=str(image_path), use_transient=True, modal=True)

    assert transient_calls["count"] == 1
    assert grab_calls["count"] == 1
    assert startup_calls["count"] == 1


def test_context_edit_opens_editor_and_refreshes_on_save(monkeypatch) -> None:
    panel = ImageBrowserPanel.__new__(ImageBrowserPanel)
    panel._context_item = ImageResult(path="/tmp/picture.png", name="picture")

    refreshed = {"count": 0}
    panel._apply_filters_and_render = lambda: refreshed.__setitem__("count", refreshed["count"] + 1)

    created = {}

    def _fake_editor(_parent, image_path, on_saved=None):
        created["path"] = image_path
        if callable(on_saved):
            on_saved(image_path)

    monkeypatch.setattr("modules.ui.image_library.browser_panel.ImageEditorDialog", _fake_editor)

    panel._context_edit()

    assert created["path"] == "/tmp/picture.png"
    assert refreshed["count"] == 1


def test_apply_startup_window_mode_falls_back_to_screen_geometry() -> None:
    class _Window:
        def __init__(self) -> None:
            self.state_calls: list[str] = []
            self.geometry_calls: list[str] = []

        def state(self, value: str) -> None:
            self.state_calls.append(value)
            raise RuntimeError("zoom not supported")

        def winfo_screenwidth(self) -> int:
            return 1440

        def winfo_screenheight(self) -> int:
            return 900

        def geometry(self, value: str) -> None:
            self.geometry_calls.append(value)

    window = _Window()
    apply_startup_window_mode(window)

    assert window.state_calls == ["zoomed"]
    assert window.geometry_calls == ["1440x900+0+0"]
