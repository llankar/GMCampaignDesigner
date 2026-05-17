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


def test_generic_list_context_menu_hides_merge_for_single_selection(monkeypatch):
    """Verify merge command is hidden when only one entity is selected."""
    import modules.generic.generic_list_view as list_view_module
    from modules.generic.generic_list_view import GenericListView

    created_menus = []

    class _Menu:
        def __init__(self, *args, **kwargs):
            self.labels = []
            created_menus.append(self)

        def add_command(self, **kwargs):
            self.labels.append(kwargs.get("label"))

        def add_separator(self):
            pass

        def add_cascade(self, **kwargs):
            self.labels.append(kwargs.get("label"))

        def post(self, *_args):
            pass

    class _Tree:
        def selection(self):
            return ("alpha",)

    class _Model:
        entity_type = "npcs"

    monkeypatch.setattr(list_view_module.tk, "Menu", _Menu)

    view = GenericListView.__new__(GenericListView)
    view.model_wrapper = _Model()
    view.unique_field = "Name"
    view.tree = _Tree()
    view._iid_to_item = {"alpha": {"Name": "Alpha", "Portrait": ""}}
    view._base_to_iids = {"alpha": ["alpha"]}
    view.filtered_items = [{"Name": "Alpha", "Portrait": ""}]
    view.items = view.filtered_items
    view.copied_items = []
    view.color_options = {}
    view._portrait_menu_images = []
    view._get_audio_value = lambda _item: ""

    view._show_item_menu("alpha", type("Evt", (), {"x_root": 1, "y_root": 2})())

    assert "Merge entities" not in created_menus[0].labels


def test_generic_list_context_menu_shows_merge_for_multiple_selection(monkeypatch):
    """Verify merge command is visible when multiple entities are selected."""
    import modules.generic.generic_list_view as list_view_module
    from modules.generic.generic_list_view import GenericListView

    created_menus = []

    class _Menu:
        def __init__(self, *args, **kwargs):
            self.labels = []
            created_menus.append(self)

        def add_command(self, **kwargs):
            self.labels.append(kwargs.get("label"))

        def add_separator(self):
            pass

        def add_cascade(self, **kwargs):
            self.labels.append(kwargs.get("label"))

        def post(self, *_args):
            pass

    class _Tree:
        def selection(self):
            return ("alpha", "beta")

    class _Model:
        entity_type = "npcs"

    monkeypatch.setattr(list_view_module.tk, "Menu", _Menu)

    alpha = {"Name": "Alpha", "Portrait": ""}
    beta = {"Name": "Beta", "Portrait": ""}
    view = GenericListView.__new__(GenericListView)
    view.model_wrapper = _Model()
    view.unique_field = "Name"
    view.tree = _Tree()
    view._iid_to_item = {"alpha": alpha, "beta": beta}
    view._base_to_iids = {"alpha": ["alpha"], "beta": ["beta"]}
    view.filtered_items = [alpha, beta]
    view.items = view.filtered_items
    view.copied_items = []
    view.color_options = {}
    view._portrait_menu_images = []
    view._get_audio_value = lambda _item: ""

    view._show_item_menu("alpha", type("Evt", (), {"x_root": 1, "y_root": 2})())

    assert "Merge entities" in created_menus[0].labels
