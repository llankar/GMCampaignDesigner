"""Tests for GM Table handouts page UI orchestration logic."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import modules.scenarios.gm_table.handouts.page as page_module
from modules.scenarios.gm_table.handouts.service import HandoutItem


class _StringVarStub:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def _build_item(path: str) -> HandoutItem:
    return HandoutItem(
        id="NPCs:Kara:kara.png",
        title="Kara",
        entity_type="NPCs",
        source_name="Kara",
        path=path,
        kind="portrait",
        subtitle="NPC",
    )


def test_compute_columns_scales_with_available_width() -> None:
    assert page_module.GMTableHandoutsPage._compute_columns(130) == 1
    assert page_module.GMTableHandoutsPage._compute_columns(320) == 2
    assert page_module.GMTableHandoutsPage._compute_columns(620) == 3


def test_refresh_recollects_items_and_renders(monkeypatch) -> None:
    collected = [_build_item("/tmp/kara.png")]
    calls = []

    def _fake_collect(scenario_item, wrappers, map_wrapper):
        calls.append((scenario_item, wrappers, map_wrapper))
        return collected

    view = page_module.GMTableHandoutsPage.__new__(page_module.GMTableHandoutsPage)
    view._scenario_item = {"Title": "Night Run"}
    view._wrappers = {"NPCs": object()}
    view._map_wrapper = object()
    view._status_var = _StringVarStub()
    view._render_grid = lambda: calls.append("rendered")

    monkeypatch.setattr(page_module, "collect_scenario_handouts", _fake_collect)

    page_module.GMTableHandoutsPage.refresh(view)

    assert view._handouts == collected
    assert calls[0][0] == {"Title": "Night Run"}
    assert calls[-1] == "rendered"


def test_open_handout_shows_warning_without_blocking_when_file_is_missing(tmp_path) -> None:
    missing = tmp_path / "missing.png"
    handout = _build_item(str(missing))

    view = page_module.GMTableHandoutsPage.__new__(page_module.GMTableHandoutsPage)
    view._status_var = _StringVarStub()
    view._selected_id = ""
    triggered = []
    view._render_grid = lambda: triggered.append("render")
    view._highlight_selected = lambda: triggered.append("highlight")

    page_module.GMTableHandoutsPage._open_handout(view, handout)

    assert "Missing file" in view._status_var.value
    assert triggered == ["render"]


def test_open_handout_uses_image_viewer_for_existing_file(monkeypatch, tmp_path) -> None:
    real_path = tmp_path / "existing.png"
    real_path.write_bytes(b"png")
    handout = _build_item(str(real_path))

    calls = []
    view = page_module.GMTableHandoutsPage.__new__(page_module.GMTableHandoutsPage)
    view._status_var = _StringVarStub()
    view._selected_id = ""
    view._highlight_selected = lambda: calls.append("highlight")

    monkeypatch.setattr(page_module, "show_portrait", lambda path, title=None: calls.append((path, title)))

    page_module.GMTableHandoutsPage._open_handout(view, replace(handout, title="Kara Voss"))

    assert view._selected_id == handout.id
    assert calls[0] == "highlight"
    assert calls[1] == (str(Path(real_path).resolve()), "Kara Voss")
