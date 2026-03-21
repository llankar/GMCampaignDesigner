from __future__ import annotations

import sys
import types
from types import SimpleNamespace

class _FakePilImage:
    def __init__(self, size=(64, 64), color="red"):
        self.size = size
        self.color = color

    def copy(self):
        return _FakePilImage(size=self.size, color=self.color)


if "PIL" not in sys.modules:
    pil_module = types.ModuleType("PIL")
    pil_imageops_module = types.ModuleType("PIL.ImageOps")
    pil_imagetk_module = types.ModuleType("PIL.ImageTk")

    def _contain(image, target_size):
        width, height = image.size
        bound_w, bound_h = target_size
        scale = min(bound_w / width, bound_h / height)
        resized = (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
        )
        return _FakePilImage(size=resized, color=image.color)

    pil_imageops_module.contain = _contain
    pil_imagetk_module.PhotoImage = lambda image: image
    pil_module.ImageOps = pil_imageops_module
    pil_module.ImageTk = pil_imagetk_module
    sys.modules["PIL"] = pil_module
    sys.modules["PIL.ImageOps"] = pil_imageops_module
    sys.modules["PIL.ImageTk"] = pil_imagetk_module

from PIL import ImageTk  # noqa: F401  # ensure stubbed submodule is importable

if "customtkinter" not in sys.modules:
    ctk_stub = types.ModuleType("customtkinter")

    class _Widget:
        def __init__(self, *args, **kwargs):
            pass

        def configure(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

    ctk_stub.CTkButton = _Widget
    ctk_stub.CTkFrame = _Widget
    ctk_stub.CTkImage = lambda light_image=None, dark_image=None, size=None: SimpleNamespace(
        _light_image=light_image,
        _dark_image=dark_image,
        _size=size,
    )
    sys.modules["customtkinter"] = ctk_stub

from modules.ui.menu.menu_image_adapter import prepare_menu_image, resize_ctk_icon
from modules.ui.menu.top_nav_bar import AppMenuBar


class _FakeMenu:
    def __init__(self):
        self.commands = []
        self.separators = 0

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_separator(self):
        self.separators += 1


class _FakeIcon:
    def __init__(self, size=(18, 18)):
        self._light_image = _FakePilImage(size=(64, 64), color="red")
        self._size = size


def test_prepare_menu_image_converts_ctk_style_image(monkeypatch):
    captured = {}

    def _fake_photo_image(image):
        captured["image"] = image
        return "tk-photo"

    monkeypatch.setattr("modules.ui.menu.menu_image_adapter.ImageTk.PhotoImage", _fake_photo_image)

    result = prepare_menu_image(_FakeIcon(size=(20, 12)))

    assert result == "tk-photo"
    assert captured["image"].size == (12, 12)


def test_resize_ctk_icon_returns_compact_clone():
    resized = resize_ctk_icon(_FakeIcon(size=(60, 60)), (32, 20))

    assert resized._size == (32, 20)
    assert resized._light_image.size == (20, 20)


def test_populate_submenu_uses_tk_compatible_images(monkeypatch):
    sentinel_image = object()
    monkeypatch.setattr("modules.ui.menu.top_nav_bar.prepare_menu_image", lambda icon: sentinel_image)

    bar = AppMenuBar.__new__(AppMenuBar)
    bar.app = SimpleNamespace(icons={"gm_screen": _FakeIcon()})
    bar._menu_images = []

    submenu = _FakeMenu()
    menu_spec = SimpleNamespace(
        groups=[
            SimpleNamespace(
                title="Workspace",
                helper="test helper",
                items=[
                    SimpleNamespace(
                        label="Open GM Screen",
                        shortcut="F1",
                        command=lambda: None,
                        icon_key="gm_screen",
                    )
                ],
            )
        ]
    )

    bar._populate_submenu(submenu, menu_spec)

    assert submenu.commands[2]["image"] is sentinel_image
    assert submenu.commands[2]["compound"] == "left"
    assert bar._menu_images == [sentinel_image]
