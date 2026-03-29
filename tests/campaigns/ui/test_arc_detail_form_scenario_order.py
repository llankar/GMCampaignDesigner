from modules.campaigns.ui.arc_studio.detail_form import ArcDetailForm


class _FakeListbox:
    def __init__(self, items=None, selection_index=None):
        self.items = list(items or [])
        self.selection_index = selection_index
        self.state = "normal"
        self.active_index = None

    def curselection(self):
        if self.selection_index is None:
            return ()
        return (self.selection_index,)

    def cget(self, key):
        if key == "state":
            return self.state
        raise KeyError(key)

    def delete(self, start, end=None):
        if start == 0 and end == "end":
            self.items = []
            self.selection_index = None
            return
        if isinstance(start, int) and 0 <= start < len(self.items):
            del self.items[start]
            if self.selection_index is not None:
                if self.selection_index >= len(self.items):
                    self.selection_index = len(self.items) - 1 if self.items else None

    def insert(self, _index, value):
        self.items.append(value)

    def selection_set(self, index):
        self.selection_index = index

    def selection_clear(self, _start, _end):
        self.selection_index = None

    def activate(self, index):
        self.active_index = index


class _FakeButton:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


class _FakeScenarioVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def _build_form(items, selected_index):
    form = ArcDetailForm.__new__(ArcDetailForm)
    form._scenario_items = list(items)
    form.scenarios_list = _FakeListbox(items=items, selection_index=selected_index)
    form.remove_scenario_btn = _FakeButton()
    form.move_scenario_up_btn = _FakeButton()
    form.move_scenario_down_btn = _FakeButton()
    form.sort_scenarios_btn = _FakeButton()
    form.clear_scenarios_btn = _FakeButton()
    form.scenario_entry_var = _FakeScenarioVar("")
    form._notify_calls = 0
    form._notify_change = lambda: setattr(form, "_notify_calls", form._notify_calls + 1)
    form._get_available_scenarios = lambda: []
    return form


def test_move_selected_scenario_up_reorders_and_keeps_selection():
    form = _build_form(["Alpha", "Bravo", "Charlie"], selected_index=1)

    form._move_selected_scenario_up()

    assert form._scenario_items == ["Bravo", "Alpha", "Charlie"]
    assert form.scenarios_list.selection_index == 0
    assert form._notify_calls == 1


def test_move_selected_scenario_down_reorders_and_keeps_selection():
    form = _build_form(["Alpha", "Bravo", "Charlie"], selected_index=1)

    form._move_selected_scenario_down()

    assert form._scenario_items == ["Alpha", "Charlie", "Bravo"]
    assert form.scenarios_list.selection_index == 2
    assert form._notify_calls == 1


def test_sort_scenarios_preserves_selected_title():
    form = _build_form(["Zulu", "alpha", "Bravo"], selected_index=0)

    form._sort_scenarios()

    assert form._scenario_items == ["alpha", "Bravo", "Zulu"]
    assert form.scenarios_list.selection_index == 2
    assert form._notify_calls == 1


def test_clear_scenarios_empties_list_and_notifies():
    form = _build_form(["Alpha"], selected_index=0)

    form._clear_scenarios()

    assert form._scenario_items == []
    assert form.scenarios_list.items == []
    assert form.scenarios_list.selection_index is None
    assert form._notify_calls == 1


def test_sync_remove_button_state_handles_move_actions():
    form = _build_form(["Alpha", "Bravo", "Charlie"], selected_index=1)

    form._sync_remove_button_state()
    assert form.remove_scenario_btn.state == "normal"
    assert form.move_scenario_up_btn.state == "normal"
    assert form.move_scenario_down_btn.state == "normal"
    assert form.sort_scenarios_btn.state == "normal"
    assert form.clear_scenarios_btn.state == "normal"

    form.scenarios_list.selection_index = 0
    form._sync_remove_button_state()
    assert form.move_scenario_up_btn.state == "disabled"
    assert form.move_scenario_down_btn.state == "normal"

    form.scenarios_list.selection_index = 2
    form._sync_remove_button_state()
    assert form.move_scenario_up_btn.state == "normal"
    assert form.move_scenario_down_btn.state == "disabled"


def test_add_scenario_from_picker_adds_selected_value(monkeypatch):
    form = _build_form(["Alpha"], selected_index=None)
    form._get_available_scenarios = lambda: ["Alpha", "Bravo", "Charlie"]

    monkeypatch.setattr("modules.campaigns.ui.arc_studio.detail_form.choose_scenario", lambda _master, _titles: "Bravo")

    form._add_scenario_from_picker()

    assert form._scenario_items == ["Alpha", "Bravo"]
    assert form.scenarios_list.items == ["Alpha", "Bravo"]
    assert form._notify_calls == 1


def test_add_scenario_from_picker_falls_back_to_entry_when_no_candidates():
    form = _build_form(["Alpha"], selected_index=None)
    form._get_available_scenarios = lambda: ["Alpha"]
    form.scenario_entry_var.set("Beta")

    form._add_scenario_from_picker()

    assert form._scenario_items == ["Alpha", "Beta"]
    assert form.scenarios_list.items == ["Alpha", "Beta"]
