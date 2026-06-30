from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.gm_table.fixed_overlay.models import FixedOverlayState
from modules.scenarios.gm_table.fixed_overlay import view as fixed_overlay_view
from modules.scenarios.gm_table.fixed_overlay.view import (
    COLLAPSED_TAB_TEXT,
    EXPANDED_TAB_TEXT,
    FixedOverlayView,
    TAB_WIDTH,
)


class _FakeGridWidget:
    def __init__(self, name: str = "widget", call_order: list[str] | None = None) -> None:
        self.name = name
        self.call_order = call_order
        self.removed = False
        self.shown = False
        self.grid_options: dict[str, object] = {}

    def grid_remove(self) -> None:
        if self.call_order is not None:
            self.call_order.append(f"{self.name}.grid_remove")
        self.removed = True

    def grid(self, **kwargs: object) -> None:
        if self.call_order is not None:
            self.call_order.append(f"{self.name}.grid")
        self.shown = True
        self.removed = False
        self.grid_options.update(kwargs)

    def grid_info(self) -> dict[str, object]:
        return dict(self.grid_options)


class _FakeButton(_FakeGridWidget):
    def __init__(self, name: str = "button", call_order: list[str] | None = None) -> None:
        super().__init__(name, call_order)
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        if self.call_order is not None:
            self.call_order.append(f"{self.name}.configure:{kwargs.get('text')}")
        self.options.update(kwargs)


class _FakeFixedOverlay:
    def __init__(self) -> None:
        self._state = FixedOverlayState(width=420, collapsed=False, visible=True)
        self.call_order: list[str] = []
        self.content = _FakeGridWidget("content", self.call_order)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.resize_handle = _FakeGridWidget("resize_handle", self.call_order)
        self.resize_handle.grid(row=0, column=1, sticky="ns")
        self.tab_button = _FakeButton("tab_button", self.call_order)
        self.tab_button.grid(row=0, column=2, sticky="ns")
        self.call_order.clear()
        self.configured_width = None
        self.place_calls: list[dict[str, object]] = []
        self.hidden = False
        self.lifted = False

    def configure(self, **kwargs: object) -> None:
        self.call_order.append(f"configure:{kwargs.get('width')}")
        self.configured_width = kwargs.get("width")

    def place(self, **kwargs: object) -> None:
        self.call_order.append(f"place:{kwargs.get('width')}")
        self.place_calls.append(kwargs)

    def place_forget(self) -> None:
        self.hidden = True

    def lift(self) -> None:
        self.lifted = True


def test_refresh_geometry_places_expanded_width() -> None:
    overlay = _FakeFixedOverlay()

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.configured_width == 420
    assert overlay.place_calls == [{"x": 0, "y": 0, "width": 420, "relheight": 1.0}]
    assert overlay.content.shown is True
    assert overlay.resize_handle.shown is True
    assert overlay.tab_button.options["text"] == EXPANDED_TAB_TEXT
    assert overlay.tab_button.grid_info()["column"] == 2
    assert overlay.tab_button.removed is False
    assert overlay.lifted is True


def test_refresh_geometry_uses_tab_width_when_collapsed() -> None:
    overlay = _FakeFixedOverlay()
    overlay._state = FixedOverlayState(width=420, collapsed=True, visible=True)

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.configured_width == TAB_WIDTH
    assert overlay.place_calls == [{"x": 0, "y": 0, "width": TAB_WIDTH, "relheight": 1.0}]
    assert overlay.content.removed is True
    assert overlay.resize_handle.removed is True
    assert overlay.tab_button.options["text"] == COLLAPSED_TAB_TEXT
    assert overlay.tab_button.grid_info()["column"] == 2
    assert overlay.tab_button.removed is False


def test_refresh_geometry_preserves_placed_width_across_toggles() -> None:
    overlay = _FakeFixedOverlay()

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]
    assert overlay.configured_width == 420

    overlay._state.collapsed = True
    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]
    assert overlay.configured_width == TAB_WIDTH
    assert overlay.content.removed is True
    assert overlay.resize_handle.removed is True
    assert overlay.tab_button.removed is False

    overlay._state.collapsed = False
    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]
    assert overlay.configured_width == 420
    assert overlay.place_calls[-1] == {"x": 0, "y": 0, "width": 420, "relheight": 1.0}
    assert overlay.call_order[-6:] == [
        "content.grid",
        "resize_handle.grid",
        "tab_button.grid",
        f"tab_button.configure:{EXPANDED_TAB_TEXT}",
        "configure:420",
        "place:420",
    ]
    assert overlay.content.grid_info() == {"row": 0, "column": 0, "sticky": "nsew"}
    assert overlay.resize_handle.grid_info() == {"row": 0, "column": 1, "sticky": "ns"}
    assert overlay.tab_button.grid_info() == {"row": 0, "column": 2, "sticky": "ns"}
    assert overlay.content.removed is False
    assert overlay.resize_handle.removed is False
    assert overlay.tab_button.removed is False


def test_refresh_geometry_hides_invisible_overlay() -> None:
    overlay = _FakeFixedOverlay()
    overlay._state = SimpleNamespace(visible=False)

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.hidden is True
    assert overlay.place_calls == []


class _FakeCtkWidget(_FakeGridWidget):
    def __init__(self, master=None, **kwargs: object) -> None:
        super().__init__()
        self.master = master
        self.kwargs = kwargs
        self.column_weights: dict[int, int] = {}
        self.row_weights: dict[int, int] = {}
        self.bindings: list[tuple[object, object, object]] = []
        self.packed = False

    def grid_columnconfigure(self, column: int, weight: int) -> None:
        self.column_weights[column] = weight

    def grid_rowconfigure(self, row: int, weight: int) -> None:
        self.row_weights[row] = weight

    def bind(self, sequence: object, callback: object, add: object = None) -> None:
        self.bindings.append((sequence, callback, add))

    def pack(self, **kwargs: object) -> None:
        self.packed = True
        self.pack_options = kwargs


class _FakeCtkButton(_FakeCtkWidget):
    pass


class _FakeShell:
    def __init__(self) -> None:
        self.column_weights: dict[int, int] = {}
        self.row_weights: dict[int, int] = {}

    def grid_columnconfigure(self, column: int, weight: int) -> None:
        self.column_weights[column] = weight

    def grid_rowconfigure(self, row: int, weight: int) -> None:
        self.row_weights[row] = weight

    def toggle_collapsed(self) -> None:
        pass

    def collapse(self) -> None:
        pass

    def _start_resize(self, _event: object) -> str:
        return "break"

    def _drag_resize(self, _event: object) -> str:
        return "break"

    def _finish_resize(self, _event: object) -> str:
        return "break"


def test_build_shell_places_tab_in_rightmost_column(monkeypatch) -> None:
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkScrollableFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkButton", _FakeCtkButton)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkLabel", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFont", lambda **kwargs: kwargs)
    overlay = _FakeShell()

    FixedOverlayView._build_shell(overlay)  # type: ignore[arg-type]

    assert overlay.column_weights == {0: 1, 1: 0, 2: 0}
    assert overlay.content.grid_info()["column"] == 0
    assert overlay.resize_handle.grid_info()["column"] == 1
    assert overlay.tab_button.grid_info()["column"] == 2
    assert overlay.tab_button.kwargs["text"] == COLLAPSED_TAB_TEXT
