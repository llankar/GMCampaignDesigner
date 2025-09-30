from types import SimpleNamespace

import pytest


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

    def pack(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass

    def grid_rowconfigure(self, *args, **kwargs):
        pass

    def grid_columnconfigure(self, *args, **kwargs):
        pass

    def configure(self, *args, **kwargs):
        pass

    def bind(self, *args, **kwargs):
        pass

    def delete(self, *args, **kwargs):
        pass

    def insert(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return ""


class _DummyStringVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        pass


class _DummyToplevel(_DummyWidget):
    def title(self, *args, **kwargs):
        pass

    def geometry(self, *args, **kwargs):
        pass

    def minsize(self, *args, **kwargs):
        pass

    def transient(self, *args, **kwargs):
        pass


dummy_ctk = SimpleNamespace(
    CTkFrame=_DummyWidget,
    CTkLabel=_DummyWidget,
    CTkTextbox=_DummyWidget,
    CTkFont=lambda *args, **kwargs: None,
    CTkEntry=_DummyWidget,
    StringVar=_DummyStringVar,
    CTkButton=_DummyWidget,
    CTkOptionMenu=_DummyWidget,
    CTkScrollableFrame=_DummyWidget,
    CTkToplevel=_DummyToplevel,
)


import sys

sys.modules.setdefault("customtkinter", dummy_ctk)

from modules.scenarios.scenario_builder_wizard import ScenarioBuilderWizard, messagebox


class DummyStep:
    def save_state(self, state):
        state.setdefault("Title", state.get("Title", ""))
        return True


@pytest.fixture
def wizard():
    instance = ScenarioBuilderWizard.__new__(ScenarioBuilderWizard)
    instance.steps = [("Step", DummyStep())]
    instance.current_step_index = 0
    instance.state = {
        "Title": "Test Scenario",
        "Summary": "",
        "Secrets": "",
        "Scenes": [],
        "Places": [],
        "NPCs": [],
        "Creatures": [],
        "Factions": [],
        "Objects": [],
    }

    instance.scenario_wrapper = SimpleNamespace(
        load_items=lambda: [],
        save_items=lambda items: None,
    )
    instance.on_saved = lambda: None

    destroyed_state = {"called": False}

    def destroy():
        destroyed_state["called"] = True

    instance.destroy = destroy
    instance._destroy_state = destroyed_state
    return instance


def test_finish_does_not_close_wizard_when_save_fails(monkeypatch, wizard):
    errors = []
    infos = []

    monkeypatch.setattr(messagebox, "showerror", lambda title, message: errors.append((title, message)))
    monkeypatch.setattr(messagebox, "showinfo", lambda title, message: infos.append((title, message)))

    def failing_save(_items):
        raise RuntimeError("disk full")

    wizard.scenario_wrapper = SimpleNamespace(load_items=lambda: [], save_items=failing_save)

    saved_called = {"value": False}

    def on_saved():
        saved_called["value"] = True

    wizard.on_saved = on_saved

    wizard.finish()

    assert errors, "Expected an error message when saving fails"
    assert errors[0][0] == "Scenario Save Failed"
    assert "disk full" in errors[0][1]
    assert not infos, "Success message should not be shown when saving fails"
    assert not wizard._destroy_state["called"]
    assert not saved_called["value"]
