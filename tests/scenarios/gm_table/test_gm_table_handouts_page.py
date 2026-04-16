"""Tests for GM Table handouts page rendering and interactions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import modules.scenarios.gm_table.handouts.page as page_module
from modules.scenarios.gm_table.handouts.service import HandoutItem


class _Var:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class _Widget:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.children = []
        self.bindings = {}
        if args and hasattr(args[0], "children"):
            args[0].children.append(self)

    def grid(self, **kwargs) -> None:
        self.grid_kwargs = kwargs

    def grid_propagate(self, _flag: bool) -> None:
        return None

    def bind(self, event, callback) -> None:
        self.bindings[event] = callback

    def winfo_children(self):
        return list(self.children)

    def destroy(self) -> None:
        self.destroyed = True

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)

    def grid_columnconfigure(self, *_args, **_kwargs) -> None:
        return None


class _GridFrame:
    def __init__(self) -> None:
        self.children = []

    def winfo_children(self):
        return list(self.children)

    def grid_columnconfigure(self, *_args, **_kwargs) -> None:
        return None


def _item(path: str, *, handout_id: str = "NPCs:Kara:kara.png", title: str = "Kara") -> HandoutItem:
    return HandoutItem(
        id=handout_id,
        title=title,
        entity_type="NPCs",
        source_name=title,
        path=path,
        kind="portrait",
        subtitle="NPC",
    )


def test_render_grid_shows_empty_state_when_no_handouts(monkeypatch) -> None:
    labels = []

    class _Label(_Widget):
        def __init__(self, *args, **kwargs) -> None:
            labels.append(kwargs.get("text"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(page_module.ctk, "CTkLabel", _Label)

    view = page_module.GMTableHandoutsPage.__new__(page_module.GMTableHandoutsPage)
    view._grid_frame = _GridFrame()
    view._visible_cards = {}
    view._query_var = _Var("")
    view._handouts = []
    view._column_count = 2

    page_module.GMTableHandoutsPage._render_grid(view)

    assert labels[-1] == "No scenario handouts found."


def test_render_grid_builds_compact_cards_for_collected_handouts() -> None:
    created = []

    class _Card:
        def __init__(self, handout_id: str) -> None:
            self.handout_id = handout_id
            self.grid_calls = []

        def grid(self, **kwargs) -> None:
            self.grid_calls.append(kwargs)

    def _build(master, handout):
        card = _Card(handout.id)
        created.append(card)
        return card

    view = page_module.GMTableHandoutsPage.__new__(page_module.GMTableHandoutsPage)
    view._grid_frame = _GridFrame()
    view._visible_cards = {}
    view._query_var = _Var("")
    view._column_count = 2
    view._highlight_selected = lambda: created.append("highlight")
    view._build_card = _build
    view._handouts = [
        _item("/tmp/a.png", handout_id="one"),
        _item("/tmp/b.png", handout_id="two"),
        _item("/tmp/c.png", handout_id="three"),
    ]

    page_module.GMTableHandoutsPage._render_grid(view)

    assert [card.handout_id for card in created if hasattr(card, "handout_id")] == ["one", "two", "three"]
    assert created[0].grid_calls[0]["row"] == 0
    assert created[1].grid_calls[0]["column"] == 1
    assert created[2].grid_calls[0]["row"] == 1
    assert set(view._visible_cards.keys()) == {"one", "two", "three"}


def test_clicking_card_opens_portrait_with_expected_path_and_title(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "kara.png"
    image_path.write_bytes(b"png")
    handout = _item(str(image_path), title="Kara Voss")

    monkeypatch.setattr(page_module.ctk, "CTkFrame", _Widget)
    monkeypatch.setattr(page_module.ctk, "CTkLabel", _Widget)
    monkeypatch.setattr(page_module.ctk, "CTkFont", lambda **_kwargs: object())

    shown = []
    monkeypatch.setattr(page_module, "show_portrait", lambda path, title=None: shown.append((path, title)))

    view = page_module.GMTableHandoutsPage.__new__(page_module.GMTableHandoutsPage)
    view._status_var = _Var("")
    view._selected_id = ""
    view._highlight_selected = lambda: None
    view._get_thumbnail = lambda _path: (object(), False)

    card = page_module.GMTableHandoutsPage._build_card(view, _GridFrame(), replace(handout))
    card.bindings["<Button-1>"](None)

    assert shown == [(str(Path(image_path).resolve()), "Kara Voss")]
    assert view._selected_id == handout.id
