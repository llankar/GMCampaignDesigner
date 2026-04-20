"""Tests for entities group card layout helpers."""

from modules.scenarios.widgets.scene_body.entities_group_card import _estimate_columns, _reflow_chips


class _FakeWidget:
    def __init__(self, reqwidth: int) -> None:
        self._reqwidth = reqwidth
        self.grid_calls = []
        self.grid_forget_calls = 0

    def winfo_reqwidth(self) -> int:
        return self._reqwidth

    def grid_forget(self) -> None:
        self.grid_forget_calls += 1

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(kwargs)


class _FakeContainer:
    def __init__(self, width: int, children: list[_FakeWidget]) -> None:
        self._width = width
        self._children = children

    def update_idletasks(self) -> None:
        return None

    def winfo_width(self) -> int:
        return self._width

    def winfo_reqwidth(self) -> int:
        return self._width

    def winfo_children(self) -> list[_FakeWidget]:
        return self._children


def test_estimate_columns_respects_narrow_viewport() -> None:
    """Narrow containers should reduce chip columns."""
    widgets = [_FakeWidget(120), _FakeWidget(130), _FakeWidget(125)]

    columns = _estimate_columns(220, widgets)

    assert columns == 1


def test_reflow_chips_places_all_entities_and_toggle_in_order() -> None:
    """The final "+N more" control should be the last visible grid element."""
    visible_widgets = [
        _FakeWidget(110),
        _FakeWidget(115),
        _FakeWidget(120),
        _FakeWidget(118),
    ]
    toggle_widget = _FakeWidget(90)
    ordered_widgets = [*visible_widgets, toggle_widget]
    container = _FakeContainer(width=250, children=ordered_widgets)

    _reflow_chips(container, ordered_widgets)

    for widget in ordered_widgets:
        assert widget.grid_calls, "Every visible item should be placed in the grid"

    last_call = toggle_widget.grid_calls[-1]
    assert last_call["row"] >= 1, "Narrow viewport should wrap to multiple rows"
    assert last_call["column"] == 0, "Toggle button should remain the last grid item"
