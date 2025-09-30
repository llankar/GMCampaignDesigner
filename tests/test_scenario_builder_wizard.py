import sys
import types


if "customtkinter" not in sys.modules:
    stub = types.ModuleType("customtkinter")

    class _BaseWidget:
        def __init__(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def place(self, *args, **kwargs):
            pass

        def grid_rowconfigure(self, *args, **kwargs):
            pass

        def grid_columnconfigure(self, *args, **kwargs):
            pass

        def configure(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

    class _Textbox(_BaseWidget):
        def delete(self, *args, **kwargs):
            pass

        def insert(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return ""

    class _StringVar:
        def __init__(self, value=""):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    class _Font:
        def __init__(self, *args, **kwargs):
            pass

    stub.CTkFrame = _BaseWidget
    stub.CTkLabel = _BaseWidget
    stub.CTkEntry = _BaseWidget
    stub.CTkTextbox = _Textbox
    stub.CTkButton = _BaseWidget
    stub.CTkToplevel = _BaseWidget
    stub.CTkFont = _Font
    stub.StringVar = _StringVar

    sys.modules["customtkinter"] = stub


from modules.scenarios import scenario_builder_wizard


ScenarioBuilderWizard = scenario_builder_wizard.ScenarioBuilderWizard


class DummyStep:
    def save_state(self, state):
        return True


class DummyWrapper:
    def __init__(self, items=None):
        self._items = items or []
        self.saved_items = None

    def load_items(self):
        return list(self._items)

    def save_items(self, items):
        self.saved_items = items


def test_finish_sanitises_and_warns_on_malformed_scenes(monkeypatch):
    wizard = ScenarioBuilderWizard.__new__(ScenarioBuilderWizard)
    wizard.state = {
        "Title": "Test Scenario",
        "Summary": "Overview",
        "Secrets": "Secret",
        "Scenes": [
            {
                "Title": " Opening ",
                "Summary": "  Something happens  ",
                "Text": None,
                "NPCs": ["Alice", "  ", "Alice"],
                "Places": ("City", "Docks", "City"),
                "NextScenes": ["Second", "  ", "Second"],
                "SceneType": "Intro",
                "ExtraField": "ignored",
            },
            {
                "Title": "",
                "Summary": None,
                "Text": "   Another scene   ",
                "Creatures": ("Wolf", "", "Wolf"),
                "Places": "Castle",
            },
            None,
        ],
        "Places": ["City"],
        "NPCs": ["Existing"],
        "Creatures": [],
        "Factions": [],
        "Objects": [],
    }
    wizard.steps = [(None, DummyStep())]
    wizard.current_step_index = 0
    wizard.on_saved = None
    wizard.destroy = types.MethodType(lambda self: None, wizard)

    wrapper = DummyWrapper()
    wizard.scenario_wrapper = wrapper

    warnings = []
    infos = []

    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showwarning", lambda title, msg: warnings.append((title, msg)))
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "showinfo", lambda title, msg: infos.append((title, msg)))
    monkeypatch.setattr(scenario_builder_wizard.messagebox, "askyesno", lambda *args, **kwargs: True)

    wizard.finish()

    assert wrapper.saved_items is not None
    assert len(wrapper.saved_items) == 1

    saved_scenario = wrapper.saved_items[0]
    scenes = saved_scenario["Scenes"]
    assert len(scenes) == 2

    first_scene = scenes[0]
    assert first_scene == {
        "Title": "Opening",
        "Summary": "Something happens",
        "Text": "Something happens",
        "NPCs": ["Alice"],
        "Places": ["City", "Docks"],
        "NextScenes": ["Second"],
        "Links": [{"target": "Second", "text": "Second"}],
        "SceneType": "Intro",
        "Type": "Intro",
    }

    second_scene = scenes[1]
    assert second_scene == {
        "Title": "Scene 2",
        "Summary": "Another scene",
        "Text": "Another scene",
        "Creatures": ["Wolf"],
        "Places": ["Castle"],
    }

    assert warnings and "Scene #3" in warnings[0][1]
    assert infos and "Scenario 'Test Scenario' has been saved." in infos[0][1]

