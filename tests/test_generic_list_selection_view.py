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
