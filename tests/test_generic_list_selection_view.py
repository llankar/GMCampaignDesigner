"""Regression tests for generic list selection view."""

import tkinter as tk

from modules.generic.generic_list_selection_view import GenericListSelectionView


class _StubMaster:
    def __init__(self):
        """Initialize the _StubMaster instance."""
        self.destroy_called = False

    def destroy(self):
        """Handle destroy."""
        self.destroy_called = True


def test_select_entity_closes_host_toplevel(monkeypatch):
    """Verify that select entity closes host toplevel."""
    monkeypatch.setattr(tk, "Toplevel", _StubMaster)

    master = _StubMaster()
    selected = []

    view = GenericListSelectionView.__new__(GenericListSelectionView)
    view.master = master
    view.entity_type = "scenarios"
    view.on_select_callback = lambda entity_type, name: selected.append((entity_type, name))
    view.destroy = lambda: None

    view.select_entity({"Title": "Scenario A"})

    assert selected == [("scenarios", "Scenario A")]
    assert master.destroy_called is True


def test_on_double_click_open_selected_mode_uses_open_selected():
    """Verify that on double click open selected mode uses open selected."""
    class _Tree:
        def identify_row(self, _y):
            """Handle identify row."""
            return "row-1"

        def focus(self):
            """Handle focus."""
            return ""

        def selection_set(self, iid):
            """Handle selection set."""
            self.selected = iid

    view = GenericListSelectionView.__new__(GenericListSelectionView)
    view.tree = _Tree()
    view.double_click_action = "open_selected"
    called = []
    view.open_selected = lambda: called.append("opened")
    view.item_by_id = {"row-1": {"Name": "Alpha"}}

    view.on_double_click(type("Evt", (), {"y": 10})())

    assert called == ["opened"]
