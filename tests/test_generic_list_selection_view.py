import tkinter as tk

from modules.generic.generic_list_selection_view import GenericListSelectionView


class _StubMaster:
    def __init__(self):
        self.destroy_called = False

    def destroy(self):
        self.destroy_called = True


def test_select_entity_closes_host_toplevel(monkeypatch):
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
    class _Tree:
        def identify_row(self, _y):
            return "row-1"

        def focus(self):
            return ""

        def selection_set(self, iid):
            self.selected = iid

    view = GenericListSelectionView.__new__(GenericListSelectionView)
    view.tree = _Tree()
    view.double_click_action = "open_selected"
    called = []
    view.open_selected = lambda: called.append("opened")
    view.item_by_id = {"row-1": {"Name": "Alpha"}}

    view.on_double_click(type("Evt", (), {"y": 10})())

    assert called == ["opened"]
