from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.gm_table.fixed_overlay.models import FixedOverlayState
from modules.scenarios.gm_table.fixed_overlay.view import FixedOverlayView, TAB_WIDTH


class _FakeGridWidget:
    def __init__(self) -> None:
        self.removed = False
        self.shown = False

    def grid_remove(self) -> None:
        self.removed = True

    def grid(self) -> None:
        self.shown = True


class _FakeButton:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


class _FakeFixedOverlay:
    def __init__(self) -> None:
        self._state = FixedOverlayState(width=420, collapsed=False, visible=True)
        self.content = _FakeGridWidget()
        self.resize_handle = _FakeGridWidget()
        self.tab_button = _FakeButton()
        self.configured_width = None
        self.place_calls: list[dict[str, object]] = []
        self.hidden = False
        self.lifted = False

    def configure(self, **kwargs: object) -> None:
        self.configured_width = kwargs.get("width")

    def place(self, **kwargs: object) -> None:
        if "width" in kwargs or "height" in kwargs:
            raise AssertionError("FixedOverlayView.place() must not receive width/height")
        self.place_calls.append(kwargs)

    def place_forget(self) -> None:
        self.hidden = True

    def lift(self) -> None:
        self.lifted = True


def test_refresh_geometry_configures_width_without_place_dimensions() -> None:
    overlay = _FakeFixedOverlay()

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.configured_width == 420
    assert overlay.place_calls == [{"x": 0, "y": 0, "relheight": 1.0}]
    assert overlay.content.shown is True
    assert overlay.resize_handle.shown is True
    assert overlay.tab_button.options["text"] == "‹"
    assert overlay.lifted is True


def test_refresh_geometry_uses_tab_width_when_collapsed() -> None:
    overlay = _FakeFixedOverlay()
    overlay._state = FixedOverlayState(width=420, collapsed=True, visible=True)

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.configured_width == TAB_WIDTH
    assert overlay.place_calls == [{"x": 0, "y": 0, "relheight": 1.0}]
    assert overlay.content.removed is True
    assert overlay.resize_handle.removed is True
    assert overlay.tab_button.options["text"] == "›"


def test_refresh_geometry_hides_invisible_overlay() -> None:
    overlay = _FakeFixedOverlay()
    overlay._state = SimpleNamespace(visible=False)

    FixedOverlayView._refresh_geometry(overlay)  # type: ignore[arg-type]

    assert overlay.hidden is True
    assert overlay.place_calls == []
