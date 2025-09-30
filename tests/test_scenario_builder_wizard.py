import sqlite3
import sys
from types import SimpleNamespace

import pytest


class _StubWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        def _method(*_args, **_kwargs):
            return None

        return _method

    # Common tkinter widget methods used during class definitions.
    def grid(self, *args, **kwargs):
        return None

    def pack(self, *args, **kwargs):
        return None

    def place(self, *args, **kwargs):
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None

    def insert(self, *args, **kwargs):
        return None

    def delete(self, *args, **kwargs):
        return None

    def tkraise(self, *args, **kwargs):
        return None


class _StubToplevel(_StubWidget):
    def transient(self, *args, **kwargs):
        return None

    def geometry(self, *args, **kwargs):
        return None

    def minsize(self, *args, **kwargs):
        return None

    def title(self, *args, **kwargs):
        return None


class _StubFont:
    def __init__(self, *args, **kwargs):
        pass


class _StubVariable:
    def __init__(self, value=""):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


class _FakeCTkModule(SimpleNamespace):
    def __getattr__(self, name):
        return _StubWidget


sys.modules.setdefault(
    "customtkinter",
    _FakeCTkModule(
        CTkToplevel=_StubToplevel,
        CTkFrame=_StubWidget,
        CTkLabel=_StubWidget,
        CTkTextbox=_StubWidget,
        CTkEntry=_StubWidget,
        CTkButton=_StubWidget,
        CTkFont=_StubFont,
        StringVar=_StubVariable,
    ),
)

from modules.scenarios import scenario_builder_wizard


class _DummyStep:
    def save_state(self, state):
        return True


class _DummyButton:
    def __init__(self):
        self._state = "normal"

    def cget(self, key):
        return self._state if key == "state" else None

    def configure(self, **kwargs):
        if "state" in kwargs:
            self._state = kwargs["state"]


def test_finish_shows_retry_dialog_on_load_failure(monkeypatch):
    wizard = scenario_builder_wizard.ScenarioBuilderWizard.__new__(
        scenario_builder_wizard.ScenarioBuilderWizard
    )
    wizard.current_step_index = 0
    wizard.steps = [("Review", _DummyStep())]
    wizard.wizard_state = {
        "Title": "Broken Scenario",
        "Summary": "",
        "Secrets": "",
        "Scenes": [],
        "Places": [],
        "NPCs": [],
        "Creatures": [],
        "Factions": [],
        "Objects": [],
    }
    wizard.on_saved = None
    wizard.destroy = lambda: None
    wizard.back_btn = _DummyButton()
    wizard.next_btn = _DummyButton()
    wizard.finish_btn = _DummyButton()
    wizard.cancel_btn = _DummyButton()

    load_calls = []

    def failing_load_items():
        load_calls.append(True)
        raise sqlite3.DatabaseError("db down")

    wizard.scenario_wrapper = type("Wrapper", (), {"load_items": staticmethod(failing_load_items)})()

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showinfo", lambda *args, **kwargs: None)

    dialog_calls = []

    def fake_retry_cancel(title, message):
        dialog_calls.append((title, message))
        return False

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askretrycancel", fake_retry_cancel)

    logged_messages = []

    def fake_log_exception(message, *, func_name=None):
        logged_messages.append((message, func_name))

    monkeypatch.setattr(scenario_builder_wizard, "log_exception", fake_log_exception)

    wizard.finish()

    assert dialog_calls == [("Load Error", "An error occurred while loading scenarios. Retry?")]
    assert load_calls == [True]
    assert logged_messages == [
        ("Failed to load scenarios for ScenarioBuilderWizard.", "ScenarioBuilderWizard.finish")
    ]
