import random
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


def test_new_climax_structures_drive_scene_generation():
    step = epic_finale_planner.FinaleBlueprintStep.__new__(
        epic_finale_planner.FinaleBlueprintStep
    )

    structure = epic_finale_planner.CLIMAX_STRUCTURES[-1]
    step.climax_var = _StubVariable(structure["name"])
    step.callback_var = _StubVariable(epic_finale_planner.CALLBACK_TACTICS[0])
    step.escalation_var = _StubVariable(epic_finale_planner.STAKE_ESCALATIONS[0])
    step.location_var = _StubVariable("")
    step.title_var = _StubVariable("")
    step.entity_selectors = {}

    scenario = step._build_scenario_from_config()

    assert f"Structure: {structure['name']}" in scenario["Summary"]
    assert len(scenario["Scenes"]) == len(structure["beats"])

    for scene, beat in zip(scenario["Scenes"], structure["beats"]):
        assert beat in scene["Summary"]
        assert scene["Summary"] == scene["Text"]


def test_escalation_summary_and_secrets_alignment():
    step = epic_finale_planner.FinaleBlueprintStep.__new__(
        epic_finale_planner.FinaleBlueprintStep
    )

    step.climax_var = _StubVariable(epic_finale_planner.CLIMAX_STRUCTURES[1]["name"])
    step.callback_var = _StubVariable(epic_finale_planner.CALLBACK_TACTICS[0])
    step.escalation_var = _StubVariable(epic_finale_planner.STAKE_ESCALATIONS[-1])
    step.location_var = _StubVariable("Stormwracked Expanse")
    step.title_var = _StubVariable("")
    step.entity_selectors = {}

    scenario = step._build_scenario_from_config()

    escalation_text = epic_finale_planner.STAKE_ESCALATIONS[-1]
    assert escalation_text in scenario["Summary"]

    secrets_lines = scenario["Secrets"].splitlines()
    assert secrets_lines[0] == escalation_text
    assert secrets_lines[1] == epic_finale_planner.CALLBACK_TACTICS[0]


def test_gm_guidance_surfaces_entity_secrets_and_motivations():
    step = epic_finale_planner.FinaleBlueprintStep.__new__(
        epic_finale_planner.FinaleBlueprintStep
    )

    structure = epic_finale_planner.CLIMAX_STRUCTURES[0]
    step.climax_var = _StubVariable(structure["name"])
    step.callback_var = _StubVariable(epic_finale_planner.CALLBACK_TACTICS[2])
    step.escalation_var = _StubVariable(epic_finale_planner.STAKE_ESCALATIONS[1])
    step.location_var = _StubVariable("Sky Citadel")
    step.title_var = _StubVariable("")

    selections = {
        "antagonists": ["Shadow Queen"],
        "allied_factions": ["Silent Hand"],
        "npc_allies": ["Sir Galen"],
    }
    step._collect_entity_selector_values = lambda key: selections.get(key, [])

    step.npcs = [
        {"Name": "Shadow Queen", "Secret": "She is a dragon in disguise."},
        {"Name": "Sir Galen", "Motivation": "Redeem his failures."},
    ]
    step.factions = [
        {"Name": "Silent Hand", "Secrets": "Their bargains empower fiendish allies."}
    ]
    step.places = [
        {"Title": "Sky Citadel", "Secrets": "Conceals a dormant planar gate."}
    ]
    step.entity_selectors = {}

    scenario = step._build_scenario_from_config()

    gm_guidance_lines = [
        line for line in scenario["Summary"].splitlines() if line.startswith("GM Guidance:")
    ]
    assert len(gm_guidance_lines) >= 3
    assert any("Shadow Queen" in line and "secret" in line.lower() for line in gm_guidance_lines)
    assert any("Sir Galen" in line and "motivation" in line.lower() for line in gm_guidance_lines)
    assert any("Sky Citadel" in line for line in gm_guidance_lines)

    secrets_lines = scenario["Secrets"].splitlines()
    for guidance in gm_guidance_lines:
        assert guidance in secrets_lines

    scene_texts = [scene["Summary"] for scene in scenario["Scenes"]]
    assert any("Shadow Queen" in text for text in scene_texts)
    assert any("Sir Galen" in text for text in scene_texts)


def test_random_rotation_cycles_entities_per_scene():
    step = epic_finale_planner.FinaleBlueprintStep.__new__(
        epic_finale_planner.FinaleBlueprintStep
    )

    structure = epic_finale_planner.CLIMAX_STRUCTURES[0]
    step.climax_var = _StubVariable(structure["name"])
    step.callback_var = _StubVariable(epic_finale_planner.CALLBACK_TACTICS[0])
    step.escalation_var = _StubVariable(epic_finale_planner.STAKE_ESCALATIONS[0])
    step.location_var = _StubVariable("Sky Citadel")
    step.title_var = _StubVariable("")
    step.entity_selectors = {}

    selections = {
        "antagonists": ["Shadow Queen", "Frost King", "Ember Warden"],
        "allied_factions": ["Silent Hand", "Iron Banner"],
        "npc_allies": ["Sir Galen", "Mira", "Thalia"],
    }

    step._collect_entity_selector_values = lambda key: list(selections.get(key, []))
    step._get_rng_for_generation = lambda: random.Random(7)

    scenario = step._build_scenario_from_config()

    focused_pairs = [
        tuple(scene["NPCs"]) for scene in scenario["Scenes"] if scene.get("NPCs")
    ]
    focused_factions = [
        scene["Factions"] for scene in scenario["Scenes"] if scene.get("Factions")
    ]

    highlighted_antagonists = [pair[0] for pair in focused_pairs if pair]
    highlighted_allies = [pair[1] for pair in focused_pairs if len(pair) > 1]
    highlighted_factions = [factions[0] for factions in focused_factions if factions]

    assert len(set(highlighted_antagonists)) >= 2
    assert len(set(highlighted_allies)) >= 2
    assert len(set(highlighted_factions)) >= 2

    expected_npc_order = []
    for pair in focused_pairs:
        expected_npc_order.extend(pair)

    dedup_npcs = []
    seen_npcs = set()
    for name in expected_npc_order:
        if name and name not in seen_npcs:
            seen_npcs.add(name)
            dedup_npcs.append(name)

    expected_faction_order = []
    for factions in focused_factions:
        expected_faction_order.extend(factions)

    dedup_factions = []
    seen_factions = set()
    for name in expected_faction_order:
        if name and name not in seen_factions:
            seen_factions.add(name)
            dedup_factions.append(name)

    assert scenario["NPCs"] == dedup_npcs
    assert scenario["Factions"] == dedup_factions
