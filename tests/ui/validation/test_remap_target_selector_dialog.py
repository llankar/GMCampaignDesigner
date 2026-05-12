"""Tests for remap target selector search behavior."""

from src.ui.validation.dialogs.remap_target_filter import (
    filter_remap_target_display_values,
)
from src.ui.validation.dialogs.remap_target_selector_dialog import (
    RemapTargetOption,
    RemapTargetSelectorDialog,
)
from src.validation.reference_validator import EntityRecord


class _FakeVariable:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _FakeWidget:
    def __init__(self):
        self.config = {}

    def configure(self, **kwargs):
        self.config.update(kwargs)


def _entity(identifier, label, path=()):
    return EntityRecord(
        entity_type="scenario",
        identifier=identifier,
        label=label,
        node={},
        path=tuple(path),
        parent_path=(),
        parent_type=None,
        parent_identifier=None,
        order=0,
    )


def test_filter_remap_target_display_values_matches_name_id_and_path_terms():
    values = (
        "Open the Vault (S1) — Campaign > Arc One",
        "Talk to the Bishop (S2) — Campaign > Cathedral",
        "Ambush at Docks (S3) — Campaign > Harbor",
    )

    assert filter_remap_target_display_values(values, "bishop") == (values[1],)
    assert filter_remap_target_display_values(values, "s3 harbor") == (values[2],)
    assert filter_remap_target_display_values(values, "  ") == values
    assert filter_remap_target_display_values(values, "missing") == ()


def test_dialog_search_updates_options_status_and_selected_target():
    first = RemapTargetOption(_entity("S1", "Open the Vault", ("Arc One",)))
    second = RemapTargetOption(_entity("S2", "Talk to the Bishop", ("Cathedral",)))
    dialog = RemapTargetSelectorDialog(None, (first, second))
    dropdown = _FakeWidget()
    status_label = _FakeWidget()
    remap_button = _FakeWidget()
    dialog._target_dropdown = dropdown
    dialog._search_status_label = status_label
    dialog._remap_button = remap_button
    dialog._selected_text = _FakeVariable(first.display_text)
    dialog._search_text = _FakeVariable("bishop")

    dialog._on_search_changed()

    assert dropdown.config["values"] == (second.display_text,)
    assert dialog._selected_text.get() == ""
    assert status_label.config["text"] == ""
    assert remap_button.config["state"] == "disabled"

    dialog._selected_text.set(second.display_text)
    dialog._on_selection_changed(second.display_text)
    dialog.remap()

    assert dialog.selected_target == second.entity


def test_dialog_search_reports_no_results():
    target = RemapTargetOption(_entity("S1", "Open the Vault"))
    dialog = RemapTargetSelectorDialog(None, (target,))
    dropdown = _FakeWidget()
    status_label = _FakeWidget()
    remap_button = _FakeWidget()
    dialog._target_dropdown = dropdown
    dialog._search_status_label = status_label
    dialog._remap_button = remap_button
    dialog._selected_text = _FakeVariable(target.display_text)
    dialog._search_text = _FakeVariable("zzzz")

    dialog._on_search_changed()

    assert dropdown.config["values"] == ()
    assert status_label.config["text"] == "No targets match your search."
    assert remap_button.config["state"] == "disabled"
