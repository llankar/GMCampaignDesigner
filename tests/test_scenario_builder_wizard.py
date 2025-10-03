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

_fake_resampling = SimpleNamespace(LANCZOS="LANCZOS")
class _StubImage(SimpleNamespace):
    def __init__(self, size=(0, 0)):
        super().__init__()
        self._size = size

    def filter(self, *_args, **_kwargs):
        return self

    def width(self):  # pragma: no cover - defensive
        return self._size[0]

    def height(self):  # pragma: no cover - defensive
        return self._size[1]


def _new_image(_mode="RGBA", size=(0, 0), _color=None):  # pragma: no cover - defensive stub
    return _StubImage(size=size)


class _StubImageDraw(SimpleNamespace):
    def Draw(self, _image):  # pragma: no cover - defensive
        return SimpleNamespace(
            line=lambda *args, **kwargs: None,
            ellipse=lambda *args, **kwargs: None,
            rounded_rectangle=lambda *args, **kwargs: None,
        )


class _StubImageFilter(SimpleNamespace):
    def GaussianBlur(self, radius):  # pragma: no cover - defensive
        return ("GaussianBlur", radius)


_fake_image_module = SimpleNamespace(
    Resampling=_fake_resampling,
    LANCZOS="LANCZOS",
    new=_new_image,
)
_fake_imagetk_module = SimpleNamespace(PhotoImage=_StubWidget)
_fake_image_draw = _StubImageDraw()
_fake_image_filter = _StubImageFilter()
_fake_pil_module = SimpleNamespace(
    Image=_fake_image_module,
    ImageTk=_fake_imagetk_module,
    ImageDraw=_fake_image_draw,
    ImageFilter=_fake_image_filter,
    Resampling=_fake_resampling,
    LANCZOS="LANCZOS",
)
sys.modules.setdefault("PIL", _fake_pil_module)
sys.modules.setdefault("PIL.Image", _fake_image_module)
sys.modules.setdefault("PIL.ImageTk", _fake_imagetk_module)
sys.modules.setdefault("PIL.ImageDraw", _fake_image_draw)
sys.modules.setdefault("PIL.ImageFilter", _fake_image_filter)
_fake_image_grab = SimpleNamespace(grab=lambda *args, **kwargs: None)
sys.modules.setdefault("PIL.ImageGrab", _fake_image_grab)
setattr(_fake_pil_module, "ImageGrab", _fake_image_grab)


class _StubRequests(SimpleNamespace):
    def __getattr__(self, name):  # pragma: no cover - defensive stub
        def _method(*_args, **_kwargs):
            raise RuntimeError("Stubbed requests method accessed: {}".format(name))

        return _method


sys.modules.setdefault("requests", _StubRequests())
sys.modules.setdefault("winsound", SimpleNamespace(PlaySound=lambda *args, **kwargs: None))

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


def _build_scenes_step():
    step = scenario_builder_wizard.ScenesPlanningStep.__new__(
        scenario_builder_wizard.ScenesPlanningStep
    )
    return step


def test_normalise_scene_uses_description_when_summary_missing():
    step = _build_scenes_step()
    entry = {"Description": "A lengthy description of the scene."}

    scene = step._normalise_scene(entry, 0)

    assert scene["Summary"] == "A lengthy description of the scene."


def test_normalise_scene_collects_nested_text_fragments():
    step = _build_scenes_step()
    entry = {
        "SceneText": {"text": "First part."},
        "Notes": ["Second part.", {"extra": "Third part."}],
    }

    scene = step._normalise_scene(entry, 1)

    assert scene["Summary"] == "First part.\n\nSecond part.\n\nThird part."
