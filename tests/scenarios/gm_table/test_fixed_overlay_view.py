from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.gm_table.fixed_overlay.models import (
    FixedOverlayItem,
    FixedOverlayState,
)
from modules.scenarios.gm_table.fixed_overlay import view as fixed_overlay_view
from modules.scenarios.gm_table.fixed_overlay.style import (
    OVERLAY_OPACITY,
    OVERLAY_OPACITY_OPTIONS,
    OVERLAY_TRANSPARENCY,
    blend_hex_color,
    opacity_to_label,
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
        self.show_calls = 0

    def configure(self, **kwargs: object) -> None:
        self.call_order.append(f"configure:{kwargs.get('width')}")
        self.configured_width = kwargs.get("width")

    def place(self, **kwargs: object) -> None:
        self.call_order.append(f"place:{kwargs.get('width')}")
        self.place_calls.append(kwargs)

    def place_forget(self) -> None:
        self.hidden = True

    def show(self) -> bool:
        self.call_order.append("show")
        self.show_calls += 1
        return True

    def lift(self) -> None:
        self.call_order.append("lift")
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
    assert overlay.show_calls == 1
    assert overlay.lifted is True


def test_refresh_geometry_shows_overlay_host_before_lifting() -> None:
    overlay = _FakeFixedOverlay()

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.call_order[-2:] == ["show", "lift"]


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
    assert overlay.tab_button.grid_info()["column"] == 0
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
    assert overlay.tab_button.grid_info()["column"] == 0
    assert overlay.tab_button.removed is False

    overlay._state.collapsed = False
    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]
    assert overlay.configured_width == 420
    assert overlay.place_calls[-1] == _expected_place_options(420)
    assert overlay.call_order[-8:] == [
        "content.grid",
        "resize_handle.grid",
        "tab_button.grid",
        f"tab_button.configure:{EXPANDED_TAB_TEXT}",
        "configure:420",
        "place:420",
        "show",
        "lift",
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
        self.configure_calls: list[dict[str, object]] = []
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

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)
        self.kwargs.update(kwargs)

    def pack(self, **kwargs: object) -> None:
        self.packed = True
        self.pack_options = kwargs

    def winfo_children(self) -> list[object]:
        return []

    def destroy(self) -> None:
        self.destroyed = True


class _FakeCtkButton(_FakeCtkWidget):
    pass


class _FakeCtkOptionMenu(_FakeCtkWidget):
    def __init__(self, master=None, **kwargs: object) -> None:
        super().__init__(master, **kwargs)
        self.set_calls: list[str] = []

    def set(self, value: str) -> None:
        self.set_calls.append(value)


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
        self._state = FixedOverlayState()
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

    def _current_opacity(self) -> float:
        return fixed_overlay_view.FixedOverlayView._current_opacity(self)

    def _handle_opacity_selected(self, _label: str) -> None:
        pass

    def _start_resize(self, _event: object) -> str:
        return "break"

    def _drag_resize(self, _event: object) -> str:
        return "break"

    def _finish_resize(self, _event: object) -> str:
        return "break"


def test_fixed_overlay_style_blends_at_eighty_five_percent_opacity() -> None:
    assert OVERLAY_OPACITY == 0.85
    assert OVERLAY_TRANSPARENCY == 0.15
    assert blend_hex_color("#000000", "#FFFFFF", OVERLAY_OPACITY) == "#262626"


def test_fixed_overlay_default_state_starts_expanded() -> None:
    state = FixedOverlayState.from_dict(None)

    assert state.visible is True
    assert state.collapsed is False
    assert state.opacity == OVERLAY_OPACITY


def test_fixed_overlay_state_restores_supported_opacity() -> None:
    state = FixedOverlayState.from_dict({"opacity": 0.6})

    assert state.opacity == 0.6
    assert state.to_dict()["opacity"] == 0.6


def test_fixed_overlay_init_shows_default_visible_overlay(monkeypatch) -> None:
    layers: list[object] = []

    class _FakeTransparentOverlayWindow:
        def __init__(
            self, _master: object, *, background: str, opacity: float = OVERLAY_OPACITY
        ) -> None:
            self.background = background
            self.opacity = opacity
            self.shell = _FakeCtkWidget()
            self.support = SimpleNamespace(mode="fake")
            self.configure_calls: list[dict[str, object]] = []
            self.place_calls: list[dict[str, object]] = []
            self.opacity_calls: list[float] = []
            self.sync_calls = 0
            self.show_calls = 0
            self.lift_calls = 0
            layers.append(self)

        def configure(self, **kwargs: object) -> None:
            self.configure_calls.append(kwargs)

        def place_configure(self, **kwargs: object) -> None:
            self.place_calls.append(kwargs)

        def set_opacity(self, opacity: float) -> None:
            self.opacity_calls.append(opacity)

        def sync_to_anchor(self) -> bool:
            self.sync_calls += 1
            return True

        def show(self) -> bool:
            self.show_calls += 1
            return True

        def lift(self) -> None:
            self.lift_calls += 1

        def destroy(self) -> None:
            pass

    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkScrollableFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkButton", _FakeCtkButton)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkOptionMenu", _FakeCtkOptionMenu)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkLabel", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFont", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        fixed_overlay_view,
        "TransparentOverlayWindow",
        _FakeTransparentOverlayWindow,
    )
    monkeypatch.setattr(
        fixed_overlay_view.theme_manager,
        "register_theme_change_listener",
        lambda _callback: lambda: None,
    )

    overlay = FixedOverlayView(object(), panel_builder=lambda *_args: None)

    layer = layers[0]
    assert layer.opacity == OVERLAY_OPACITY
    assert layer.opacity_calls == [OVERLAY_OPACITY]
    assert layer.place_calls == [_expected_place_options(300)]
    assert layer.show_calls == 1
    assert layer.lift_calls == 1

    overlay.destroy()


def test_build_shell_places_tab_in_rightmost_column(monkeypatch) -> None:
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkScrollableFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkButton", _FakeCtkButton)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkOptionMenu", _FakeCtkOptionMenu)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkLabel", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFont", lambda **kwargs: kwargs)
    overlay = _FakeShell()

    FixedOverlayView._build_shell(overlay)  # type: ignore[arg-type]

    assert overlay.column_weights == {0: 1, 1: 0, 2: 0}
    assert overlay.content.grid_info()["column"] == 0
    assert overlay.resize_handle.grid_info()["column"] == 1
    assert overlay.tab_button.grid_info()["column"] == 2
    assert overlay.tab_button.kwargs["text"] == EXPANDED_TAB_TEXT
    assert overlay.opacity_menu.grid_info()["column"] == 1
    assert overlay.opacity_menu.kwargs["values"] == [
        opacity_to_label(value) for value in OVERLAY_OPACITY_OPTIONS
    ]
    assert overlay.opacity_menu.kwargs["command"] == overlay._handle_opacity_selected
    assert overlay.add_button.grid_info()["column"] == 2
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


def test_fixed_overlay_state_serializes_geometry_and_items() -> None:
    state = FixedOverlayState(
        visible=True,
        collapsed=False,
        width=9999,
        selected_item_ids=["item-a"],
        items=[
            FixedOverlayItem(
                item_id="item-a",
                kind="note",
                title="Pinned Note",
                state={"fixed_overlay_width": 512, "fixed_overlay_height": 384},
            )
        ],
    )

    payload = state.to_dict()

    assert payload["collapsed"] is False
    assert payload["width"] == 1100
    assert payload["opacity"] == OVERLAY_OPACITY
    assert payload["items"] == [
        {
            "item_id": "item-a",
            "kind": "note",
            "title": "Pinned Note",
            "state": {"fixed_overlay_width": 512, "fixed_overlay_height": 384},
        }
    ]


def test_item_dimensions_clamp_collapsed_and_expanded_geometry() -> None:
    tiny = FixedOverlayItem(
        item_id="tiny",
        kind="note",
        title="Tiny",
        state={"fixed_overlay_width": 1, "fixed_overlay_height": 1},
    )
    huge = FixedOverlayItem(
        item_id="huge",
        kind="note",
        title="Huge",
        state={"fixed_overlay_width": 5000, "fixed_overlay_height": 900},
    )

    assert FixedOverlayView._item_dimensions(tiny) == (240, 140)
    assert FixedOverlayView._item_dimensions(huge) == (1052, 900)


class _AttributesFailWindow:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def attributes(self, *args: object) -> None:
        self.calls.append(args)
        raise fixed_overlay_view.tk.TclError("unsupported")


def test_transparent_overlay_window_reports_graceful_fallback() -> None:
    from modules.scenarios.gm_table.fixed_overlay.overlay_window import (
        TransparentOverlayWindow,
    )

    fake = SimpleNamespace(window=_AttributesFailWindow())

    support = TransparentOverlayWindow._configure_transparency(fake)  # type: ignore[arg-type]

    assert support.mode == "fallback"
    assert support.true_transparency is False
    assert fake.window.calls == [
        ("-alpha", OVERLAY_OPACITY),
        ("-transparentcolor", "#010203"),
    ]


def test_fixed_overlay_state_clamps_width_to_header_controls_minimum() -> None:
    state = FixedOverlayState(width=1)

    assert state.to_dict()["width"] == 300


def test_transparent_overlay_window_prefers_window_alpha_for_opacity() -> None:
    from modules.scenarios.gm_table.fixed_overlay.overlay_window import (
        TransparentOverlayWindow,
    )

    class _AttributesWindow:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []

        def attributes(self, *args: object) -> None:
            self.calls.append(args)

    fake = SimpleNamespace(window=_AttributesWindow())

    support = TransparentOverlayWindow._configure_transparency(fake)  # type: ignore[arg-type]

    assert support.mode == "alpha"
    assert support.true_transparency is True
    assert fake.window.calls == [("-alpha", OVERLAY_OPACITY)]


def test_transparent_overlay_window_set_opacity_updates_window_alpha() -> None:
    from modules.scenarios.gm_table.fixed_overlay.overlay_window import (
        TransparentOverlayWindow,
        TransparencySupport,
    )

    class _AttributesWindow:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []

        def attributes(self, *args: object) -> None:
            self.calls.append(args)

    fake = SimpleNamespace(
        window=_AttributesWindow(), support=TransparencySupport("alpha", True)
    )

    TransparentOverlayWindow.set_opacity(fake, 0.4)  # type: ignore[arg-type]

    assert fake._opacity == 0.4
    assert fake.window.calls == [("-alpha", 0.4)]


def test_transparent_overlay_window_shell_uses_visible_background(monkeypatch) -> None:
    from modules.scenarios.gm_table.fixed_overlay import overlay_window

    created_frames: list[object] = []

    class FakeToplevel:
        def __init__(self) -> None:
            self.configure_calls: list[dict[str, object]] = []

        def withdraw(self) -> None:
            pass

        def overrideredirect(self, _value: bool) -> None:
            pass

        def configure(self, **kwargs: object) -> None:
            self.configure_calls.append(kwargs)

        def transient(self, _master: object) -> None:
            pass

        def attributes(self, *_args: object) -> None:
            pass

    class FakeMaster:
        def winfo_toplevel(self) -> object:
            return self

        def bind(self, *_args: object, **_kwargs: object) -> None:
            pass

    class FakeFrame:
        def __init__(self, master: object, **kwargs: object) -> None:
            self.master = master
            self.kwargs = kwargs
            self.configure_calls: list[dict[str, object]] = []
            created_frames.append(self)

        def place(self, **kwargs: object) -> None:
            self.place_options = kwargs

        def configure(self, **kwargs: object) -> None:
            self.configure_calls.append(kwargs)

    monkeypatch.setattr(overlay_window.tk, "Toplevel", lambda _master: FakeToplevel())
    monkeypatch.setattr(overlay_window.ctk, "CTkFrame", FakeFrame)

    window = overlay_window.TransparentOverlayWindow(FakeMaster(), background="#ABCDEF")
    window.configure(fg_color="#FEDCBA", border_color="#123456")

    assert window.window.configure_calls[0]["background"] == "#ABCDEF"
    assert window.window.configure_calls[-1]["background"] == "#FEDCBA"
    assert created_frames[0].kwargs["fg_color"] == "#ABCDEF"
    assert created_frames[0].kwargs["border_width"] == 0
    assert created_frames[0].configure_calls[-1]["fg_color"] == "#FEDCBA"
    assert created_frames[0].configure_calls[-1]["border_color"] == "#123456"


def test_build_shell_paints_visible_full_area_hosts(monkeypatch) -> None:
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkScrollableFrame", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkButton", _FakeCtkButton)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkOptionMenu", _FakeCtkOptionMenu)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkLabel", _FakeCtkWidget)
    monkeypatch.setattr(fixed_overlay_view.ctk, "CTkFont", lambda **kwargs: kwargs)
    overlay = _FakeShell()

    FixedOverlayView._build_shell(overlay)  # type: ignore[arg-type]

    expected_surface = overlay._overlay_surface_color()
    assert overlay.content.kwargs["fg_color"] == expected_surface
    assert overlay.header.kwargs["fg_color"] == expected_surface
    assert overlay.items_host.kwargs["fg_color"] == expected_surface
    assert overlay.resize_handle.kwargs["fg_color"] == overlay._palette["panel_focus"]
    assert overlay.tab_button.kwargs["fg_color"] == overlay._palette["accent"]


def test_fixed_overlay_item_color_uses_eighty_five_percent_opacity() -> None:
    overlay = _FakeShell()

    item_color = FixedOverlayView._overlay_item_color(overlay)  # type: ignore[arg-type]

    assert item_color == blend_hex_color("#171F30", "#11141E", OVERLAY_OPACITY)
    assert item_color != overlay._palette["table_bg"]


class _OpacityLayer:
    def __init__(self) -> None:
        self.configure_calls: list[dict[str, object]] = []
        self.opacity_calls: list[float] = []

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)

    def set_opacity(self, opacity: float) -> None:
        self.opacity_calls.append(opacity)


def test_handle_opacity_selected_updates_alpha_colors_and_state() -> None:
    changed_calls: list[str] = []
    overlay = FixedOverlayView.__new__(FixedOverlayView)
    overlay._palette = {
        "panel_bg": "#0F1523",
        "panel_alt": "#171F30",
        "table_bg": "#11141E",
        "panel_focus": "#7DD3FC",
    }
    overlay._state = FixedOverlayState(opacity=OVERLAY_OPACITY)
    overlay._overlay_layer = _OpacityLayer()
    overlay.opacity_menu = _FakeCtkOptionMenu()
    overlay.content = _FakeCtkWidget()
    overlay.header = _FakeCtkWidget()
    overlay.items_host = _FakeCtkWidget()
    overlay._item_frames = {"item": _FakeCtkWidget()}
    overlay._on_changed = lambda: changed_calls.append("changed")

    FixedOverlayView._handle_opacity_selected(overlay, "60%")

    expected_surface = blend_hex_color("#0F1523", "#11141E", 0.6)
    expected_item = blend_hex_color("#171F30", "#11141E", 0.6)
    assert overlay._state.opacity == 0.6
    assert overlay._overlay_layer.opacity_calls == [0.6]
    assert overlay._overlay_layer.configure_calls[-1]["fg_color"] == expected_surface
    assert overlay.content.configure_calls[-1]["fg_color"] == expected_surface
    assert overlay.header.configure_calls[-1]["fg_color"] == expected_surface
    assert overlay.items_host.configure_calls[-1]["fg_color"] == expected_surface
    assert overlay._item_frames["item"].configure_calls[-1]["fg_color"] == expected_item
    assert overlay.opacity_menu.set_calls == ["60%"]
    assert changed_calls == ["changed"]


def test_apply_state_restores_opacity_to_control_alpha_and_colors() -> None:
    overlay = FixedOverlayView.__new__(FixedOverlayView)
    overlay._palette = {
        "panel_bg": "#0F1523",
        "panel_alt": "#171F30",
        "table_bg": "#11141E",
        "panel_focus": "#7DD3FC",
    }
    overlay._overlay_layer = _OpacityLayer()
    overlay.opacity_menu = _FakeCtkOptionMenu()
    overlay.content = _FakeCtkWidget()
    overlay.header = _FakeCtkWidget()
    overlay.items_host = _FakeCtkWidget()
    overlay._item_frames = {"item": _FakeCtkWidget()}
    overlay._refresh_items = lambda: None
    overlay._refresh_geometry = lambda: None

    FixedOverlayView.apply_state(overlay, FixedOverlayState(opacity=0.4))

    expected_surface = blend_hex_color("#0F1523", "#11141E", 0.4)
    assert overlay._state.opacity == 0.4
    assert overlay.opacity_menu.set_calls == ["40%"]
    assert overlay._overlay_layer.opacity_calls == [0.4]
    assert overlay._overlay_layer.configure_calls[-1]["fg_color"] == expected_surface


class _GeometryMaster:
    def __init__(self, *, mapped: bool, width: int, height: int) -> None:
        self.mapped = mapped
        self.width = width
        self.height = height
        self.retry_callbacks: list[object] = []
        self.cancelled: list[object] = []

    def update_idletasks(self) -> None:
        pass

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def winfo_rootx(self) -> int:
        return 10

    def winfo_rooty(self) -> int:
        return 20

    def after(self, _delay: int, callback: object) -> str:
        self.retry_callbacks.append(callback)
        return "retry-id"

    def after_cancel(self, retry_id: object) -> None:
        self.cancelled.append(retry_id)


class _GeometryWindow:
    def __init__(self) -> None:
        self.geometry_calls: list[str] = []
        self.deiconify_calls = 0
        self.withdraw_calls = 0

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def deiconify(self) -> None:
        self.deiconify_calls += 1

    def withdraw(self) -> None:
        self.withdraw_calls += 1


def _make_geometry_overlay(master: _GeometryMaster):
    from modules.scenarios.gm_table.fixed_overlay.overlay_window import (
        TransparentOverlayWindow,
    )

    overlay = TransparentOverlayWindow.__new__(TransparentOverlayWindow)
    overlay.master = master
    overlay.window = _GeometryWindow()
    overlay._width = 50
    overlay._visible = False
    overlay._destroyed = False
    overlay._geometry_retry_id = None
    overlay._anchor_sync_id = None
    overlay._place_options = {"x": 3, "y": 4}
    overlay._last_geometry_failure_reason = ""
    return overlay



class _AnchorBindingWidget:
    def __init__(self) -> None:
        self.bind_calls: list[tuple[str, object, str | None]] = []

    def bind(self, event_name: str, callback: object, add: str | None = None) -> None:
        self.bind_calls.append((event_name, callback, add))


def test_bind_anchor_events_tracks_surface_and_toplevel_events() -> None:
    from modules.scenarios.gm_table.fixed_overlay.overlay_window import (
        TransparentOverlayWindow,
    )

    surface = _AnchorBindingWidget()
    toplevel = _AnchorBindingWidget()
    surface.winfo_toplevel = lambda: toplevel  # type: ignore[attr-defined]
    overlay = TransparentOverlayWindow.__new__(TransparentOverlayWindow)
    overlay.master = surface

    TransparentOverlayWindow._bind_anchor_events(overlay)

    expected_events = ["<Map>", "<Visibility>", "<FocusIn>", "<Configure>", "<Destroy>"]
    assert [call[0] for call in surface.bind_calls] == expected_events
    assert [call[0] for call in toplevel.bind_calls] == expected_events
    assert all(call[2] == "+" for call in surface.bind_calls + toplevel.bind_calls)


def test_anchor_visibility_event_debounces_geometry_sync_without_lift() -> None:
    master = _GeometryMaster(mapped=True, width=300, height=200)
    overlay = _make_geometry_overlay(master)
    overlay._visible = True

    overlay._on_anchor_visibility_event()
    overlay._on_anchor_visibility_event()

    assert overlay._anchor_sync_id == "retry-id"
    assert len(master.retry_callbacks) == 1
    master.retry_callbacks[0]()

    assert overlay.window.geometry_calls == ["50x200+13+24"]
    assert overlay.window.deiconify_calls == 1
    assert not hasattr(overlay.window, "lift_calls")


def test_anchor_visibility_event_ignores_hidden_or_destroyed_overlay() -> None:
    master = _GeometryMaster(mapped=True, width=300, height=200)
    overlay = _make_geometry_overlay(master)

    overlay._on_anchor_visibility_event()
    overlay._destroyed = True
    overlay._visible = True
    overlay._on_anchor_visibility_event()

    assert master.retry_callbacks == []


def test_place_configure_stores_geometry_without_mapping() -> None:
    master = _GeometryMaster(mapped=True, width=300, height=200)
    overlay = _make_geometry_overlay(master)

    overlay.place_configure(width=70, x=5)

    assert overlay._visible is False
    assert overlay.window.deiconify_calls == 0
    assert overlay._place_options["x"] == 5
    assert overlay._width == 70


def test_ensure_visible_retries_until_anchor_geometry_is_ready() -> None:
    master = _GeometryMaster(mapped=False, width=1, height=1)
    overlay = _make_geometry_overlay(master)

    assert overlay.show() is False
    assert overlay._visible is True
    assert overlay.window.deiconify_calls == 0
    assert overlay._geometry_retry_id == "retry-id"
    assert overlay.last_geometry_failure_reason == "anchor is unmapped"

    master.mapped = True
    master.width = 300
    master.height = 200
    overlay._run_geometry_retry()

    assert overlay.window.geometry_calls == ["50x200+13+24"]
    assert overlay.window.deiconify_calls == 1
    assert overlay.last_geometry_failure_reason == ""


def test_ensure_visible_stops_retrying_after_destroy() -> None:
    master = _GeometryMaster(mapped=False, width=1, height=1)
    overlay = _make_geometry_overlay(master)
    overlay._visible = True
    overlay._destroyed = True

    assert overlay.ensure_visible() is False
    assert master.retry_callbacks == []
