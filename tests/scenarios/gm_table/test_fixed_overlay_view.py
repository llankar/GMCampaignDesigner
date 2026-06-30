from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.gm_table.fixed_overlay.models import (
    FixedOverlayItem,
    FixedOverlayState,
)
from modules.scenarios.gm_table.fixed_overlay import view as fixed_overlay_view
from modules.scenarios.gm_table.fixed_overlay.style import (
    OVERLAY_OPACITY,
    blend_hex_color,
)
from modules.scenarios.gm_table.fixed_overlay.view import (
    COLLAPSED_TAB_TEXT,
    EXPANDED_TAB_TEXT,
    FixedOverlayView,
    TAB_WIDTH,
)




def _expected_place_options(width: int) -> dict[str, object]:
    return {
        "x": 0,
        "y": 0,
        "relx": 0,
        "rely": 0,
        "width": width,
        "relwidth": 0,
        "relheight": 1.0,
    }


class _FakeGridWidget:
    def __init__(
        self, name: str = "widget", call_order: list[str] | None = None
    ) -> None:
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
    def __init__(
        self, name: str = "button", call_order: list[str] | None = None
    ) -> None:
        super().__init__(name, call_order)
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        if self.call_order is not None:
            self.call_order.append(f"{self.name}.configure:{kwargs.get('text')}")
        self.options.update(kwargs)


class _FakeFixedOverlay:
    def __init__(self) -> None:
        self._state = FixedOverlayState(
            width=420,
            collapsed=False,
            visible=True,
            items=[FixedOverlayItem(item_id="item", kind="note", title="Note")],
        )
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
    assert overlay.place_calls == [_expected_place_options(420)]
    assert overlay.content.shown is True
    assert overlay.resize_handle.shown is True
    assert overlay.tab_button.options["text"] == EXPANDED_TAB_TEXT
    assert overlay.tab_button.grid_info()["column"] == 2
    assert overlay.tab_button.removed is False
    assert overlay.lifted is True


def test_refresh_geometry_uses_tab_width_when_collapsed() -> None:
    overlay = _FakeFixedOverlay()
    overlay._state = FixedOverlayState(
        width=420,
        collapsed=True,
        visible=True,
        items=[FixedOverlayItem(item_id="item", kind="note", title="Note")],
    )

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.configured_width == TAB_WIDTH
    assert overlay.place_calls == [_expected_place_options(TAB_WIDTH)]
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
    assert overlay.place_calls[-1] == _expected_place_options(420)
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
        self._palette = {
            "panel_bg": "#0F1523",
            "panel_alt": "#171F30",
            "table_bg": "#11141E",
            "panel_focus": "#7DD3FC",
            "accent": "#F59E0B",
            "accent_hover": "#D97706",
            "button_text_on_accent": "#F4F7FB",
            "text": "#F4F7FB",
            "muted": "#9EABC2",
        }
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

    def _request_add(self) -> None:
        pass

    def _overlay_surface_color(self) -> str:
        return fixed_overlay_view.FixedOverlayView._overlay_surface_color(self)

    def _start_resize(self, _event: object) -> str:
        return "break"

    def _drag_resize(self, _event: object) -> str:
        return "break"

    def _finish_resize(self, _event: object) -> str:
        return "break"


def test_fixed_overlay_style_blends_at_ninety_percent_opacity() -> None:
    assert OVERLAY_OPACITY == 0.90
    assert blend_hex_color("#000000", "#FFFFFF", OVERLAY_OPACITY) == "#191919"


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
    assert overlay.add_button.grid_info()["column"] == 1
    assert overlay.add_button.kwargs["text"] == "+ Add"
    assert overlay.add_button.kwargs["command"] == overlay._request_add


def test_request_add_calls_callback_with_add_button() -> None:
    calls: list[object] = []
    overlay = SimpleNamespace(
        _on_add_requested=lambda source: calls.append(source),
        add_button=object(),
    )

    FixedOverlayView._request_add(overlay)  # type: ignore[arg-type]

    assert calls == [overlay.add_button]


def test_remove_item_deletes_item_and_persists_change() -> None:
    changed_calls: list[str] = []
    overlay = SimpleNamespace(
        _state=FixedOverlayState(
            items=[
                FixedOverlayItem(
                    item_id="keep", kind="note", title="Keep", state={"value": 1}
                ),
                FixedOverlayItem(
                    item_id="remove", kind="note", title="Remove", state={"value": 2}
                ),
            ]
        ),
        _payloads={"keep": object(), "remove": object()},
        _refresh_items=lambda: None,
        _changed=lambda: changed_calls.append("changed"),
    )

    FixedOverlayView._remove_item(overlay, "remove")  # type: ignore[arg-type]

    assert [item.item_id for item in overlay._state.items] == ["keep"]
    assert "remove" not in overlay._payloads
    assert changed_calls == ["changed"]
    assert [item["item_id"] for item in FixedOverlayView.get_state(overlay)["items"]] == ["keep"]  # type: ignore[arg-type]


def test_remove_item_ignores_unknown_item_without_change() -> None:
    changed_calls: list[str] = []
    overlay = SimpleNamespace(
        _state=FixedOverlayState(
            items=[FixedOverlayItem(item_id="keep", kind="note", title="Keep")]
        ),
        _payloads={"keep": object()},
        _refresh_items=lambda: None,
        _changed=lambda: changed_calls.append("changed"),
    )

    FixedOverlayView._remove_item(overlay, "missing")  # type: ignore[arg-type]

    assert [item.item_id for item in overlay._state.items] == ["keep"]
    assert changed_calls == []
