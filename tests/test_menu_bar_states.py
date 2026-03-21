from __future__ import annotations

import sys
import types
from types import SimpleNamespace


def _ensure_module(name: str, module: types.ModuleType) -> None:
    sys.modules.setdefault(name, module)


if "customtkinter" not in sys.modules:
    ctk_stub = types.ModuleType("customtkinter")

    class _Widget:
        def __init__(self, *args, **kwargs):
            self._config = dict(kwargs)

        def configure(self, **kwargs):
            self._config.update(kwargs)

        def cget(self, key):
            return self._config.get(key)

        def pack(self, *args, **kwargs):
            self._pack = kwargs

        def grid(self, *args, **kwargs):
            self._grid = kwargs

        def pack_configure(self, **kwargs):
            self._pack = {**getattr(self, "_pack", {}), **kwargs}

        def grid_configure(self, **kwargs):
            self._grid = {**getattr(self, "_grid", {}), **kwargs}

        def bind(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

    ctk_stub.CTkButton = _Widget
    ctk_stub.CTkFrame = _Widget
    _ensure_module("customtkinter", ctk_stub)

from modules.ui.menu.menu_visual_state import MenuLayoutController
from modules.ui.menu.top_nav_bar import AppMenuBar


class _FakeButton:
    def __init__(self, text="File"):
        self._config = {
            "text": text,
            "fg_color": "",
            "hover_color": "",
            "text_color": "",
            "border_color": "",
        }

    def configure(self, **kwargs):
        self._config.update(kwargs)

    def cget(self, key):
        return self._config.get(key)

    def pack_configure(self, **kwargs):
        self._config.setdefault('_pack', {}).update(kwargs)

    def grid_configure(self, **kwargs):
        self._config.setdefault('_grid', {}).update(kwargs)

    def winfo_rootx(self):
        return 10

    def winfo_rooty(self):
        return 20

    def winfo_height(self):
        return 12


class _FakeController:
    def __init__(self, button):
        self.button = button
        self.is_open = False
        self.is_active = False
        self.calls = []

    def apply_theme(self, palette, *, width=None):
        self.calls.append({"palette": palette, "width": width, "is_open": self.is_open, "is_active": self.is_active})


class _FakeMenu:
    def __init__(self):
        self.posted = []
        self.unposted = 0

    def post(self, x, y):
        self.posted.append((x, y))

    def unpost(self):
        self.unposted += 1

    def grab_release(self):
        pass


class _FakeFrame:
    def __init__(self):
        self.config = {}
        self.grid_updates = []
        self.pack_updates = []

    def configure(self, **kwargs):
        self.config.update(kwargs)

    def grid_configure(self, **kwargs):
        self.grid_updates.append(kwargs)

    def pack_configure(self, **kwargs):
        self.pack_updates.append(kwargs)


class _FakeChrome:
    def __init__(self):
        self.palette = None

    def apply_theme(self, palette):
        self.palette = palette


def _build_bar_for_state_tests():
    bar = AppMenuBar.__new__(AppMenuBar)
    bar._last_palette = SimpleNamespace(menu_bg="#123", button_fg="#456", button_border="#789", text_color="#EEE")
    bar._layout_mode = "expanded"
    button = _FakeButton()
    controller = _FakeController(button)
    bar._menu_controller_map = {button: controller}
    bar._open_menu_button = None
    bar._open_menu = None
    bar._button_menus = []
    bar._menu_controllers = [controller]
    return bar, button, controller


def test_popup_menu_marks_trigger_button_open_and_root_click_clears_it():
    bar, button, controller = _build_bar_for_state_tests()
    menu = _FakeMenu()
    bar._button_menus = [(button, menu)]

    bar._popup_menu(menu, button)

    assert bar._open_menu is menu
    assert bar._open_menu_button is button
    assert controller.is_open is True
    assert menu.posted == [(10, 32)]

    bar._on_root_click(SimpleNamespace(widget=object()))

    assert bar._open_menu is None
    assert bar._open_menu_button is None
    assert controller.is_open is False
    assert menu.unposted == 1


def test_popup_menu_toggles_same_button_closed():
    bar, button, controller = _build_bar_for_state_tests()
    menu = _FakeMenu()

    bar._popup_menu(menu, button)
    bar._popup_menu(menu, button)

    assert bar._open_menu is None
    assert bar._open_menu_button is None
    assert controller.is_open is False
    assert menu.unposted == 1


def test_refresh_theme_reapplies_open_and_focused_states(monkeypatch):
    bar = AppMenuBar.__new__(AppMenuBar)
    bar._layout_mode = "expanded"
    bar.app = SimpleNamespace(winfo_width=lambda: 1600)
    bar.frame = _FakeFrame()
    bar.menu_frame = _FakeFrame()
    bar.quick_actions_frame = _FakeFrame()
    bar.quick_actions_inner = _FakeFrame()
    bar.actions_frame = _FakeFrame()
    bar.system_quick_frame = _FakeFrame()
    bar.utility_actions_frame = _FakeFrame()
    bar.chrome = _FakeChrome()

    menu_button = _FakeButton("Campaign")
    menu_controller = _FakeController(menu_button)
    menu_controller.is_open = True
    quick_controller = _FakeController(_FakeButton("GM Screen"))
    quick_controller.is_focused = True

    utility_button = _FakeButton("Utility")
    bar._menu_controllers = [menu_controller]
    bar._primary_quick_controllers = [quick_controller]
    bar._system_quick_controllers = []
    bar._submenus = []
    bar._action_buttons = [utility_button]

    monkeypatch.setattr(
        "modules.ui.menu.top_nav_bar.MenuVisualPalette.from_theme",
        classmethod(lambda cls: SimpleNamespace(
            menu_bg="#001122",
            button_fg="#113355",
            button_border="#335577",
            text_color="#eef3ff",
        )),
    )

    bar.refresh_theme()

    assert menu_controller.calls, "menu controller should be restyled"
    assert menu_controller.calls[-1]["width"] >= 72
    assert quick_controller.calls, "quick action controller should be restyled"
    assert bar.chrome.palette.menu_bg == "#001122"
    assert utility_button.cget("fg_color") == "#001122"
    assert utility_button.cget("border_color") == "#335577"


def test_layout_controller_switches_between_compact_and_expanded_modes():
    compact = MenuLayoutController.resolve(1200)
    expanded = MenuLayoutController.resolve(1800)

    assert compact.mode == "compact"
    assert compact.menu_button_padx == (0, 2)
    assert expanded.mode == "expanded"
    assert expanded.menu_button_padx == (0, 6)
