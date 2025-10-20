import sys
import types


class _StubWidget:
    def __init__(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):  # pragma: no cover - defensive stub
        return None

    def pack(self, *args, **kwargs):  # pragma: no cover - defensive stub
        return None

    def place(self, *args, **kwargs):  # pragma: no cover - defensive stub
        return None

    def configure(self, *args, **kwargs):  # pragma: no cover - defensive stub
        return None


class _StubVariable:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):  # pragma: no cover - defensive stub
        self._value = value


def _ensure_customtkinter_stub():
    if "customtkinter" in sys.modules:
        return

    module = types.ModuleType("customtkinter")
    widget_type = type("_CTkWidget", (_StubWidget,), {})
    module.CTkFrame = widget_type
    module.CTkLabel = widget_type
    module.CTkTextbox = widget_type
    module.CTkEntry = widget_type
    module.CTkButton = widget_type
    module.CTkOptionMenu = widget_type
    module.CTkScrollableFrame = widget_type
    module.CTkToplevel = widget_type
    module.CTkFont = lambda *args, **kwargs: None  # pragma: no cover - defensive stub
    module.CTkImage = lambda *args, **kwargs: None  # pragma: no cover - defensive stub
    module.StringVar = _StubVariable
    sys.modules["customtkinter"] = module


def _ensure_pil_stub():
    if "PIL" in sys.modules:
        return

    pil_module = types.ModuleType("PIL")

    class _StubImage:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def resize(self, *_args, **_kwargs):  # pragma: no cover - defensive stub
            return self

        def copy(self):  # pragma: no cover - defensive stub
            return self

    class _StubImageModule(types.SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.Resampling = types.SimpleNamespace(LANCZOS="LANCZOS")
            self.LANCZOS = "LANCZOS"

        def new(self, *_args, **_kwargs):  # pragma: no cover - defensive stub
            return _StubImage()

        def open(self, *_args, **_kwargs):  # pragma: no cover - defensive stub
            return _StubImage()

    image_module = _StubImageModule()
    pil_module.Image = image_module
    sys.modules["PIL"] = pil_module
    sys.modules["PIL.Image"] = image_module
    image_tk_module = types.ModuleType("PIL.ImageTk")
    image_tk_module.PhotoImage = _StubImage  # pragma: no cover - defensive stub
    sys.modules["PIL.ImageTk"] = image_tk_module
    image_grab_module = types.ModuleType("PIL.ImageGrab")
    image_grab_module.grab = lambda *args, **kwargs: None  # pragma: no cover - defensive stub
    sys.modules["PIL.ImageGrab"] = image_grab_module
    image_draw_module = types.ModuleType("PIL.ImageDraw")
    image_draw_module.Draw = lambda *_args, **_kwargs: types.SimpleNamespace(  # pragma: no cover - defensive stub
        line=lambda *a, **k: None,
        ellipse=lambda *a, **k: None,
        rounded_rectangle=lambda *a, **k: None,
    )
    sys.modules["PIL.ImageDraw"] = image_draw_module
    image_filter_module = types.ModuleType("PIL.ImageFilter")
    image_filter_module.GaussianBlur = lambda radius: ("GaussianBlur", radius)  # pragma: no cover
    sys.modules["PIL.ImageFilter"] = image_filter_module


_ensure_customtkinter_stub()
_ensure_pil_stub()


def _ensure_requests_stub():
    if "requests" in sys.modules:
        return

    requests_module = types.ModuleType("requests")

    def _stub_method(*_args, **_kwargs):  # pragma: no cover - defensive stub
        raise RuntimeError("Stubbed requests method accessed")

    for name in ("get", "post", "put", "delete", "head", "patch"):
        setattr(requests_module, name, _stub_method)

    sys.modules["requests"] = requests_module


_ensure_requests_stub()


def _ensure_winsound_stub():
    if "winsound" in sys.modules:
        return

    winsound_module = types.ModuleType("winsound")
    winsound_module.PlaySound = lambda *args, **kwargs: None  # pragma: no cover - defensive stub
    winsound_module.SND_FILENAME = 0  # pragma: no cover - defensive stub
    winsound_module.SND_ASYNC = 0  # pragma: no cover - defensive stub
    winsound_module.SND_LOOP = 0  # pragma: no cover - defensive stub
    sys.modules["winsound"] = winsound_module


_ensure_winsound_stub()

from modules.scenarios import epic_finale_planner


def test_scenario_guidance_highlights_callback_and_escalation():
    step = epic_finale_planner.FinaleBlueprintStep.__new__(
        epic_finale_planner.FinaleBlueprintStep
    )
    step.climax_var = _StubVariable(epic_finale_planner.CLIMAX_STRUCTURES[0]["name"])
    step.callback_var = _StubVariable(epic_finale_planner.CALLBACK_TACTICS[1])
    step.escalation_var = _StubVariable(epic_finale_planner.STAKE_ESCALATIONS[2])
    step.location_var = _StubVariable("Sky Citadel")
    step.title_var = _StubVariable("")
    step.entity_selectors = {}

    scenario = step._build_scenario_from_config()

    callback_index = step._select_callback_scene_index(
        epic_finale_planner.CLIMAX_STRUCTURES[0]["beats"]
    )
    escalation_index = step._select_escalation_scene_index(
        epic_finale_planner.CLIMAX_STRUCTURES[0]["beats"], callback_index
    )

    callback_scene = scenario["Scenes"][callback_index]
    escalation_scene = scenario["Scenes"][escalation_index]

    expected_callback = (
        f"Callback Beat: {epic_finale_planner.CALLBACK_TACTICS[1]}"
    )
    expected_escalation = (
        f"Escalation Beat: {epic_finale_planner.STAKE_ESCALATIONS[2]}"
    )

    assert expected_callback in callback_scene["Summary"]
    assert expected_callback in callback_scene["Text"]
    assert callback_scene["Summary"] == callback_scene["Text"]

    assert expected_escalation in escalation_scene["Summary"]
    assert expected_escalation in escalation_scene["Text"]
    assert escalation_scene["Summary"] == escalation_scene["Text"]
