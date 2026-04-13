"""Regression tests for scenario builder wizard."""

import sqlite3
import sys
from types import SimpleNamespace

import pytest


class _StubWidget:
    def __init__(self, *args, **kwargs):
        """Initialize the _StubWidget instance."""
        pass

    def __getattr__(self, name):
        """Handle getattr."""
        def _method(*_args, **_kwargs):
            """Internal helper for method."""
            return None

        return _method

    # Common tkinter widget methods used during class definitions.
    def grid(self, *args, **kwargs):
        """Handle grid."""
        return None

    def pack(self, *args, **kwargs):
        """Pack the operation."""
        return None

    def place(self, *args, **kwargs):
        """Handle place."""
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        """Handle grid rowconfigure."""
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        """Handle grid columnconfigure."""
        return None

    def configure(self, *args, **kwargs):
        """Handle configure."""
        return None

    def insert(self, *args, **kwargs):
        """Handle insert."""
        return None

    def delete(self, *args, **kwargs):
        """Delete the operation."""
        return None

    def tkraise(self, *args, **kwargs):
        """Handle tkraise."""
        return None


class _StubToplevel(_StubWidget):
    def transient(self, *args, **kwargs):
        """Handle transient."""
        return None

    def geometry(self, *args, **kwargs):
        """Handle geometry."""
        return None

    def minsize(self, *args, **kwargs):
        """Handle minsize."""
        return None

    def title(self, *args, **kwargs):
        """Handle title."""
        return None


class _StubFont:
    def __init__(self, *args, **kwargs):
        """Initialize the _StubFont instance."""
        pass


class _StubVariable:
    def __init__(self, value=""):
        """Initialize the _StubVariable instance."""
        self._value = value

    def set(self, value):
        """Set the operation."""
        self._value = value

    def get(self):
        """Return the operation."""
        return self._value


class _FakeCTkModule(SimpleNamespace):
    def __getattr__(self, name):
        """Handle getattr."""
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
        """Initialize the _StubImage instance."""
        super().__init__()
        self._size = size

    def filter(self, *_args, **_kwargs):
        """Handle filter."""
        return self

    def width(self):  # pragma: no cover - defensive
        """Handle width."""
        return self._size[0]

    def height(self):  # pragma: no cover - defensive
        """Handle height."""
        return self._size[1]


def _new_image(_mode="RGBA", size=(0, 0), _color=None):  # pragma: no cover - defensive stub
    """Internal helper for new image."""
    return _StubImage(size=size)


class _StubImageDraw(SimpleNamespace):
    def Draw(self, _image):  # pragma: no cover - defensive
        """Handle draw."""
        return SimpleNamespace(
            line=lambda *args, **kwargs: None,
            ellipse=lambda *args, **kwargs: None,
            rounded_rectangle=lambda *args, **kwargs: None,
        )


class _StubImageFilter(SimpleNamespace):
    def GaussianBlur(self, radius):  # pragma: no cover - defensive
        """Handle gaussian blur."""
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
        """Handle getattr."""
        def _method(*_args, **_kwargs):
            """Internal helper for method."""
            raise RuntimeError("Stubbed requests method accessed: {}".format(name))

        return _method


sys.modules.setdefault("requests", _StubRequests())
sys.modules.setdefault("winsound", SimpleNamespace(PlaySound=lambda *args, **kwargs: None))

from modules.scenarios import scenario_builder_wizard


class _DummyStep:
    def save_state(self, state):
        """Save state."""
        return True


class _DummyButton:
    def __init__(self):
        """Initialize the _DummyButton instance."""
        self._state = "normal"

    def cget(self, key):
        """Handle cget."""
        return self._state if key == "state" else None

    def configure(self, **kwargs):
        """Handle configure."""
        if "state" in kwargs:
            self._state = kwargs["state"]


class _RecordingLabel:
    def __init__(self):
        """Initialize the _RecordingLabel instance."""
        self.kwargs = {}

    def configure(self, **kwargs):
        """Handle configure."""
        self.kwargs.update(kwargs)


class _RecordingTextbox:
    def __init__(self):
        """Initialize the _RecordingTextbox instance."""
        self.content = ""

    def configure(self, **_kwargs):
        """Handle configure."""
        return None

    def delete(self, *_args, **_kwargs):
        """Delete the operation."""
        self.content = ""

    def insert(self, *_args):
        """Handle insert."""
        self.content = _args[-1] if _args else ""


class _RecordingFlowPreview:
    def __init__(self):
        """Initialize the _RecordingFlowPreview instance."""
        self.calls = []

    def render(self, scenes, selected_index=None):
        """Render the operation."""
        self.calls.append((scenes, selected_index))


class _RecordingScenarioWrapper:
    def __init__(self, items=None):
        """Initialize the _RecordingScenarioWrapper instance."""
        self._items = list(items or [])
        self.saved_items = None

    def load_items(self):
        """Load items."""
        return list(self._items)

    def save_items(self, items):
        """Save items."""
        self.saved_items = list(items)


def _attach_wizard_buttons(wizard):
    """Internal helper for attach wizard buttons."""
    wizard.back_btn = _DummyButton()
    wizard.next_btn = _DummyButton()
    wizard.finish_btn = _DummyButton()
    wizard.cancel_btn = _DummyButton()
    wizard.story_forge_btn = _DummyButton()
    wizard.mode = "standalone"
    wizard.persist_on_finish = False


def test_finish_shows_retry_dialog_on_load_failure(monkeypatch):
    """Verify that finish shows retry dialog on load failure."""
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
    _attach_wizard_buttons(wizard)

    load_calls = []

    def failing_load_items():
        """Handle failing load items."""
        load_calls.append(True)
        raise sqlite3.DatabaseError("db down")

    wizard.scenario_wrapper = type("Wrapper", (), {"load_items": staticmethod(failing_load_items)})()

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showinfo", lambda *args, **kwargs: None)

    dialog_calls = []

    def fake_retry_cancel(title, message):
        """Handle fake retry cancel."""
        dialog_calls.append((title, message))
        return False

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askretrycancel", fake_retry_cancel)

    logged_messages = []

    def fake_log_exception(message, *, func_name=None):
        """Handle fake log exception."""
        logged_messages.append((message, func_name))

    monkeypatch.setattr(scenario_builder_wizard, "log_exception", fake_log_exception)

    wizard.finish()

    assert dialog_calls == [("Load Error", "An error occurred while loading scenarios. Retry?")]
    assert load_calls == [True]
    assert logged_messages == [
        ("Failed to load scenarios for ScenarioBuilderWizard.", "ScenarioBuilderWizard.finish")
    ]


def test_entity_linking_step_includes_villains_and_events():
    """Verify that entity linking step includes villains and events."""
    expected_fields = {
        "bases": ("Bases", "Base"),
        "books": ("Books", "Book"),
        "creatures": ("Creatures", "Creature"),
        "events": ("Events", "Event"),
        "factions": ("Factions", "Faction"),
        "maps": ("Maps", "Map"),
        "npcs": ("NPCs", "NPC"),
        "objects": ("Objects", "Item"),
        "pcs": ("PCs", "PC"),
        "places": ("Places", "Place"),
        "villains": ("Villains", "Villain"),
    }

    for entity_type, labels in expected_fields.items():
        assert scenario_builder_wizard.EntityLinkingStep.ENTITY_FIELDS[entity_type] == labels


def test_finish_saves_all_selected_entity_links(monkeypatch):
    """Verify that finish saves all selected entity links."""
    wizard = scenario_builder_wizard.ScenarioBuilderWizard.__new__(
        scenario_builder_wizard.ScenarioBuilderWizard
    )
    wizard.current_step_index = 0
    wizard.steps = [("Review", _DummyStep())]
    wizard.wizard_state = {
        "Title": "Linked Scenario",
        "Summary": "Summary",
        "Secrets": "Secret",
        "Scenes": [{"Title": "Intro"}],
        "Bases": [],
        "Places": ["Harbor"],
        "Maps": ["Harbor Map"],
        "NPCs": ["Morgan"],
        "PCs": ["Avery"],
        "Creatures": [],
        "Factions": [],
        "Villains": ["The Broker", "The Broker"],
        "Events": ["Festival Night", "Festival Night"],
        "Objects": [],
        "Books": ["Chronicle", "Chronicle"],
        "ScenarioCharacterGraph": {},
        "ScenarioCharacterGraphSync": False,
    }
    wizard.on_saved = None
    wizard.destroy = lambda: None
    _attach_wizard_buttons(wizard)
    wizard.scenario_wrapper = _RecordingScenarioWrapper()

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askretrycancel", lambda *args, **kwargs: True)

    wizard.finish()

    assert wizard.scenario_wrapper.saved_items is not None
    assert wizard.scenario_wrapper.saved_items[0]["Villains"] == ["The Broker"]
    assert wizard.scenario_wrapper.saved_items[0]["Events"] == ["Festival Night"]
    assert wizard.scenario_wrapper.saved_items[0]["Books"] == ["Chronicle"]


def _build_scenes_step():
    """Build scenes step."""
    step = scenario_builder_wizard.ScenesPlanningStep.__new__(
        scenario_builder_wizard.ScenesPlanningStep
    )
    return step


def test_normalise_scene_uses_description_when_summary_missing():
    """Verify that normalise scene uses description when summary missing."""
    step = _build_scenes_step()
    entry = {"Description": "A lengthy description of the scene."}

    scene = step._normalise_scene(entry, 0)

    assert scene["Summary"] == "A lengthy description of the scene."


def test_normalise_scene_collects_nested_text_fragments():
    """Verify that normalise scene collects nested text fragments."""
    step = _build_scenes_step()
    entry = {
        "SceneText": {"text": "First part."},
        "Notes": ["Second part.", {"extra": "Third part."}],
    }

    scene = step._normalise_scene(entry, 1)

    assert scene["Summary"] == "First part.\n\nSecond part.\n\nThird part."


def test_save_state_persists_structured_fields_and_composed_text():
    """Verify save_state stores structured scene fields + legacy composed text."""
    step = _build_scenes_step()
    step._collect_active_scenes = lambda: [
        {
            "Title": "Dockside Meeting",
            "Summary": "The broker arrives late.",
            "SceneType": "Social",
            "SceneBeats": ["Negotiate terms, keep cover intact"],
            "SceneClues": ["Ledger page with coded initials"],
            "LinkData": [{"target": "Ambush", "text": "Follow the courier"}],
            "_canvas": {"x": 120, "y": 90},
        }
    ]
    step.scenario_title_var = _StubVariable("Harbor Intrigue")
    step._scenario_summary = "Scenario summary"
    step._scenario_secrets = "Secret note"
    step._root_extra_fields = {}
    step.scenes = []

    state = {}
    assert step.save_state(state) is True

    persisted = state["Scenes"][0]
    assert persisted["Summary"] == "The broker arrives late."
    assert persisted["SceneBeats"] == ["Negotiate terms, keep cover intact"]
    assert persisted["SceneClues"] == ["Ledger page with coded initials"]
    assert "Key beats:" in persisted["Text"]
    assert "- Negotiate terms, keep cover intact" in persisted["Text"]


def test_scene_mode_adapters_round_trip_structured_fields():
    """Verify structured fields round-trip across guided/canvas adapters."""
    cards = [
        {
            "Title": "Hook",
            "Summary": "Start at the docks.",
            "SceneType": "Setup",
            "SceneBeats": ["Talk to Captain Rhel, avoid suspicion"],
        },
        {
            "Title": "Fallout",
            "Summary": "Deal with consequences.",
            "SceneType": "Outcome",
            "SceneClues": ["Stamped crate marked OR-17"],
        },
    ]

    scenes = scenario_builder_wizard.guided_cards_to_scenes(cards)
    assert scenes[0]["SceneBeats"] == ["Talk to Captain Rhel, avoid suspicion"]
    assert "Key beats:" in scenes[0]["Text"]

    round_tripped = scenario_builder_wizard.scenes_to_guided_cards(scenes)
    assert round_tripped[0]["SceneBeats"] == ["Talk to Captain Rhel, avoid suspicion"]
    assert round_tripped[1]["SceneClues"] == ["Stamped crate marked OR-17"]


def test_finish_embedded_can_persist_before_callback(monkeypatch):
    """Verify that finish embedded can persist before callback."""
    wizard = scenario_builder_wizard.ScenarioBuilderWizard.__new__(
        scenario_builder_wizard.ScenarioBuilderWizard
    )
    wizard.current_step_index = 0
    wizard.steps = [("Review", _DummyStep())]
    wizard.wizard_state = {
        "Title": "Arc Embedded Scenario",
        "Summary": "From Story Forge",
        "Secrets": "Twist",
        "Scenes": [{"Title": "Intro"}],
        "ScenarioCharacterGraph": {},
        "ScenarioCharacterGraphSync": False,
    }
    for field in scenario_builder_wizard.SCENARIO_ENTITY_FIELD_NAMES:
        wizard.wizard_state[field] = []
    wizard.campaign_context = {"name": "Campaign"}
    wizard.arc_context = {"name": "Arc 1"}
    wizard.on_saved = None
    wizard.destroy = lambda: None
    _attach_wizard_buttons(wizard)
    wizard.mode = "embedded"
    wizard.persist_on_finish = True
    wizard.scenario_wrapper = _RecordingScenarioWrapper(items=[{"Title": "Legacy", "Scenes": []}])

    callbacks = []
    wizard.on_embedded_result = lambda payload: callbacks.append(payload)

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askretrycancel", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        scenario_builder_wizard,
        "build_embedded_result_payload",
        lambda *_args, **_kwargs: {"scenario_title": "Arc Embedded Scenario", "scenario": {"Title": "Arc Embedded Scenario"}},
    )

    wizard.finish()

    assert wizard.scenario_wrapper.saved_items is not None
    persisted_titles = [item.get("Title") for item in wizard.scenario_wrapper.saved_items]
    assert "Arc Embedded Scenario" in persisted_titles
    assert len(callbacks) == 1


def test_load_existing_scenario_uses_selected_payload_directly():
    """Verify that load existing scenario uses selected payload directly."""
    step = _build_scenes_step()
    loaded = []
    step.scenario_wrapper = object()
    step._choose_existing_scenario = lambda: {
        "Title": "Loaded Scenario",
        "Scenes": [{"Title": "Intro", "Summary": "Opening scene"}],
        "NPCs": ["Morgan"],
    }
    step.load_from_payload = lambda scenario: loaded.append(scenario)

    step._load_existing_scenario()

    assert loaded == [
        {
            "Title": "Loaded Scenario",
            "Scenes": [{"Title": "Intro", "Summary": "Opening scene"}],
            "NPCs": ["Morgan"],
        }
    ]


def test_select_scene_entities_double_click_queues_until_apply(monkeypatch):
    """Verify that select scene entities double click queues until apply."""
    step = _build_scenes_step()
    step.entity_wrappers = {"npcs": object()}
    step.winfo_toplevel = lambda: object()

    class _Dialog:
        def __init__(self, *_args, **_kwargs):
            """Initialize the _Dialog instance."""
            self.destroyed = False

        def title(self, *_args, **_kwargs):
            """Handle title."""
            return None

        def geometry(self, *_args, **_kwargs):
            """Handle geometry."""
            return None

        def minsize(self, *_args, **_kwargs):
            """Handle minsize."""
            return None

        def transient(self, *_args, **_kwargs):
            """Handle transient."""
            return None

        def grab_set(self, *_args, **_kwargs):
            """Handle grab set."""
            return None

        def destroy(self):
            """Handle destroy."""
            self.destroyed = True

    buttons = {}
    queued_labels = []

    class _Button:
        def __init__(self, _master, text, command):
            """Initialize the _Button instance."""
            buttons[text] = command

        def pack(self, *_args, **_kwargs):
            """Pack the operation."""
            return None

    class _Label:
        def __init__(self, _master, textvariable=None, **_kwargs):
            """Initialize the _Label instance."""
            self._text_var = textvariable

        def pack(self, *_args, **_kwargs):
            """Pack the operation."""
            if self._text_var:
                queued_labels.append(self._text_var.get())
            return None

    class _SelectionView:
        def __init__(self, _dialog, _entity_type, _wrapper, _template, **kwargs):
            """Initialize the _SelectionView instance."""
            self.kwargs = kwargs
            step._selection_kwargs = kwargs
            step._on_select_callback = kwargs["on_select_callback"]

        def pack(self, *_args, **_kwargs):
            """Pack the operation."""
            return None

    monkeypatch.setattr(scenario_builder_wizard.ctk, "CTkToplevel", _Dialog)
    monkeypatch.setattr(scenario_builder_wizard.ctk, "CTkButton", _Button)
    monkeypatch.setattr(scenario_builder_wizard.ctk, "CTkLabel", _Label)
    monkeypatch.setattr(scenario_builder_wizard, "GenericListSelectionView", _SelectionView)
    monkeypatch.setattr(scenario_builder_wizard, "load_template", lambda _entity_type: {"fields": [{"name": "Name"}]})

    def _wait_window(_dialog):
        """Internal helper for wait window."""
        step._on_select_callback("npcs", "Morgan", {})
        buttons["Apply Queued Selection"]()

    step.wait_window = _wait_window

    selected = step._select_scene_entities("npcs", "NPCs", ["Avery"])

    assert selected == ["Avery", "Morgan"]
    assert step._selection_kwargs["allow_multi_select"] is True
    assert step._selection_kwargs["double_click_action"] == "emit_selection"
    assert queued_labels and "Double-click to queue, then Apply Queued Selection." in queued_labels[0]


def test_select_scene_entities_cancel_keeps_existing_state(monkeypatch):
    """Verify that select scene entities cancel keeps existing state."""
    step = _build_scenes_step()
    step.entity_wrappers = {"places": object()}
    step.winfo_toplevel = lambda: object()

    class _Dialog:
        def __init__(self, *_args, **_kwargs):
            """Initialize the _Dialog instance."""
            return None

        def title(self, *_args, **_kwargs):
            """Handle title."""
            return None

        def geometry(self, *_args, **_kwargs):
            """Handle geometry."""
            return None

        def minsize(self, *_args, **_kwargs):
            """Handle minsize."""
            return None

        def transient(self, *_args, **_kwargs):
            """Handle transient."""
            return None

        def grab_set(self, *_args, **_kwargs):
            """Handle grab set."""
            return None

        def destroy(self):
            """Handle destroy."""
            return None

    class _SelectionView:
        def __init__(self, *_args, **kwargs):
            """Initialize the _SelectionView instance."""
            step._on_select_callback = kwargs["on_select_callback"]

        def pack(self, *_args, **_kwargs):
            """Pack the operation."""
            return None

    monkeypatch.setattr(scenario_builder_wizard.ctk, "CTkToplevel", _Dialog)
    monkeypatch.setattr(scenario_builder_wizard, "GenericListSelectionView", _SelectionView)
    monkeypatch.setattr(scenario_builder_wizard, "load_template", lambda _entity_type: {"fields": [{"name": "Name"}]})

    # Keep default widget stubs for frame/label/button and exit without applying.
    step.wait_window = lambda _dialog: step._on_select_callback("places", "Dockside", {})

    selected = step._select_scene_entities("places", "Places", ["Old Town"])

    assert selected == ["Old Town"]


def test_review_step_load_state_normalises_scene_links_for_preview_render():
    """Verify that review step load state normalises scene links for preview render."""
    step = scenario_builder_wizard.ReviewStep.__new__(scenario_builder_wizard.ReviewStep)
    step.title_label = _RecordingLabel()
    step.summary_label = _RecordingLabel()
    step.secrets_label = _RecordingLabel()
    step.stats_label = _RecordingLabel()
    step.details_text = _RecordingTextbox()
    step.flow_preview = _RecordingFlowPreview()

    state = {
        "Title": "Flow Scenario",
        "Summary": "A branch-heavy outline",
        "Secrets": "Hidden agenda",
        "Scenes": [
            {
                "Title": "Arrival",
                "LinkData": [{"target": "Market", "text": "Go to market"}],
            },
            {
                "Title": "Market",
                "NextScenes": "Finale",
            },
            {
                "Title": "Finale",
                "NextScenes": "",
            },
        ],
    }

    step.load_state(state)

    assert step.flow_preview.calls, "Expected ReviewStep.load_state to call flow_preview.render"
    scenes, selected_index = step.flow_preview.calls[-1]
    assert selected_index is None
    assert scenes[0]["NextScenes"] == ["Market"]
    assert scenes[1]["NextScenes"] == ["Finale"]
    assert scenes[2]["NextScenes"] == []
