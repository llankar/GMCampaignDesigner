import sys
from types import SimpleNamespace


class _StubWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, _name):
        def _method(*_args, **_kwargs):
            return None

        return _method

    def pack(self, *args, **kwargs):
        return None


class _FakeCTkModule(SimpleNamespace):
    def __getattr__(self, _name):
        return _StubWidget


sys.modules.setdefault(
    "customtkinter",
    _FakeCTkModule(
        CTkToplevel=_StubWidget,
        CTkFrame=_StubWidget,
        CTkLabel=_StubWidget,
        CTkTextbox=_StubWidget,
        CTkEntry=_StubWidget,
        CTkButton=_StubWidget,
        CTkOptionMenu=_StubWidget,
        CTkScrollableFrame=_StubWidget,
        StringVar=lambda value="": SimpleNamespace(get=lambda: value, set=lambda *_args, **_kwargs: None),
    ),
)

from modules.campaigns.ui import campaign_builder_wizard


def test_load_existing_campaign_uses_selected_payload(monkeypatch):
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )

    chosen_payload = {"Name": "Storm Front", "Arcs": [{"name": "Act I"}]}
    applied = {}

    wizard._choose_existing_campaign = lambda: chosen_payload
    wizard._apply_campaign_to_form = lambda payload: applied.setdefault("payload", payload)
    wizard._refresh_arcs_preview = lambda: None
    wizard._refresh_review = lambda: None
    wizard._show_step = lambda _idx: None
    wizard.original_campaign_name = None

    wizard._load_existing_campaign()

    assert applied["payload"] is chosen_payload
    assert wizard.original_campaign_name == "Storm Front"


def test_load_existing_campaign_ignores_empty_selection():
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )

    wizard._choose_existing_campaign = lambda: None
    wizard._apply_campaign_to_form = lambda _payload: (_ for _ in ()).throw(
        AssertionError("Should not apply payload when nothing is selected")
    )

    wizard._load_existing_campaign()


class _FakeTextBox:
    def __init__(self, value=""):
        self.value = value

    def get(self, *_args, **_kwargs):
        return self.value

    def delete(self, *_args, **_kwargs):
        self.value = ""

    def insert(self, *_args):
        self.value = _args[-1]


class _FakeDateField:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_apply_preset_preserves_touched_fields_and_arcs():
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )
    wizard.form_vars = {
        "name": _FakeVar("Existing Name"),
        "genre": _FakeVar(""),
        "tone": _FakeVar("Custom Tone"),
        "status": _FakeVar("Planned"),
    }
    wizard.start_date_field = _FakeDateField("")
    wizard.end_date_field = _FakeDateField("")
    wizard.logline_box = _FakeTextBox("Manual logline")
    wizard.setting_box = _FakeTextBox("")
    wizard.objective_box = _FakeTextBox("")
    wizard.stakes_box = _FakeTextBox("")
    wizard.themes_box = _FakeTextBox("")
    wizard.notes_box = _FakeTextBox("")
    wizard.arcs = [{"name": "Existing Arc"}]

    preset = {
        "form": {"genre": "Fantasy", "tone": "Preset Tone", "start_date": "2026-01-01"},
        "text_areas": {"logline": "Preset logline", "themes": "Duty\nLegacy"},
        "arcs": [{"name": "Preset Arc"}],
    }

    touched_fields, touched_arcs = wizard._detect_manual_modifications()
    wizard._apply_preset(preset, touched_fields=touched_fields, preserve_arcs=touched_arcs)

    assert wizard.form_vars["genre"].get() == "Fantasy"
    assert wizard.form_vars["tone"].get() == "Custom Tone"
    assert wizard.logline_box.get("1.0", "end") == "Manual logline"
    assert wizard.themes_box.get("1.0", "end") == "Duty\nLegacy"
    assert wizard.start_date_field.get() == "2026-01-01"
    assert wizard.arcs == [{"name": "Existing Arc"}]

def test_extract_arc_index_from_preview_line_parses_order_header():
    index = campaign_builder_wizard.CampaignBuilderWizard._extract_arc_index_from_preview_line(
        "Order 3: Midnight Rising [Planned]"
    )
    assert index == 2


def test_extract_arc_index_from_preview_line_ignores_non_header_lines():
    index = campaign_builder_wizard.CampaignBuilderWizard._extract_arc_index_from_preview_line(
        "   Objective: Recover the relic"
    )
    assert index is None


def test_find_arc_index_for_line_uses_whole_arc_block_ranges():
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )
    wizard._arc_line_ranges = [
        (1, 3, 0),
        (5, 7, 1),
    ]

    assert wizard._find_arc_index_for_line(1) == 0
    assert wizard._find_arc_index_for_line(3) == 0
    assert wizard._find_arc_index_for_line(5) == 1
    assert wizard._find_arc_index_for_line(7) == 1
    assert wizard._find_arc_index_for_line(4) is None


def test_apply_generated_arcs_replaces_existing_arcs_after_ai_success():
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )
    wizard.arcs = [{"name": "Existing Arc", "summary": "", "objective": "", "status": "Planned", "thread": "Old", "scenarios": ["Old Scenario"]}]
    wizard.current_arc_index = 0
    refresh_calls = {"preview": 0, "review": 0}
    wizard._refresh_arcs_preview = lambda: refresh_calls.__setitem__("preview", refresh_calls["preview"] + 1)
    wizard._refresh_review = lambda: refresh_calls.__setitem__("review", refresh_calls["review"] + 1)

    wizard._apply_generated_arcs(
        [
            {
                "name": "Arc One",
                "summary": "Setup",
                "objective": "Investigate the guild",
                "status": "In Progress",
                "thread": "Guild War",
                "scenarios": ["Cold Open", "Hidden Ledger"],
            }
        ],
        merge=False,
    )

    assert wizard.arcs == [
        {
            "name": "Arc One",
            "summary": "Setup",
            "objective": "Investigate the guild",
            "status": "In Progress",
            "thread": "Guild War",
            "scenarios": ["Cold Open", "Hidden Ledger"],
        }
    ]
    assert wizard.current_arc_index == 0
    assert refresh_calls == {"preview": 1, "review": 1}


def test_generate_arcs_from_scenarios_applies_service_result_after_confirmation(monkeypatch):
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )
    wizard.scenario_titles = ["Cold Open"]
    wizard.scenario_wrapper = object()
    wizard.arcs = []
    wizard.form_vars = {
        "name": _FakeVar("Stormfront"),
        "genre": _FakeVar("Noir"),
        "tone": _FakeVar("Tense"),
        "status": _FakeVar("Planned"),
    }
    wizard.logline_box = _FakeTextBox("A city on the edge.")
    wizard.setting_box = _FakeTextBox("Rain-soaked towers.")
    wizard.objective_box = _FakeTextBox("Stop the syndicate war.")
    wizard.stakes_box = _FakeTextBox("The district burns.")
    wizard.themes_box = _FakeTextBox("Trust\nBetrayal")
    wizard.notes_box = _FakeTextBox("Use existing cases.")
    wizard._get_ai = lambda: object()

    applied = {}
    wizard._apply_generated_arcs = lambda arcs, merge=False: applied.update({"arcs": arcs, "merge": merge})

    class _FakeArcGenerationService:
        def __init__(self, ai_client, scenario_wrapper):
            applied["ai_client"] = ai_client
            applied["scenario_wrapper"] = scenario_wrapper

        def generate_arcs(self, foundation):
            applied["foundation"] = foundation
            return {
                "arcs": [
                    {
                        "name": "Arc One",
                        "summary": "Setup",
                        "objective": "Investigate",
                        "status": "Planned",
                        "thread": "Guild War",
                        "scenarios": ["Cold Open"],
                    }
                ]
            }

    monkeypatch.setattr(campaign_builder_wizard, "ArcGenerationService", _FakeArcGenerationService)
    monkeypatch.setattr(campaign_builder_wizard.messagebox, "showinfo", lambda *args, **kwargs: None)

    wizard._generate_arcs_from_scenarios()

    assert applied["scenario_wrapper"] is wizard.scenario_wrapper
    assert applied["foundation"] == {
        "name": "Stormfront",
        "genre": "Noir",
        "tone": "Tense",
        "status": "Planned",
        "logline": "A city on the edge.",
        "setting": "Rain-soaked towers.",
        "main_objective": "Stop the syndicate war.",
        "stakes": "The district burns.",
        "themes": ["Trust", "Betrayal"],
        "notes": "Use existing cases.",
        "existing_entities": {
            "villains": [],
            "factions": [],
            "places": [],
            "npcs": [],
            "creatures": [],
        },
    }
    assert applied["merge"] is False
    assert applied["arcs"][0]["thread"] == "Guild War"


def test_validate_arcs_for_scenario_generation_rejects_arcs_without_linked_scenarios():
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )
    wizard.arcs = [
        {
            "name": "Guild War",
            "summary": "Escalation",
            "objective": "Break the syndicate",
            "status": "Planned",
            "thread": "Hidden conspiracy",
            "scenarios": [],
        }
    ]

    try:
        wizard._validate_arcs_for_scenario_generation()
    except campaign_builder_wizard.ArcScenarioExpansionValidationError as exc:
        assert "at least one linked scenario" in str(exc)
    else:
        raise AssertionError("Expected ArcScenarioExpansionValidationError")


def test_generate_scenarios_per_arc_links_saved_titles_back_to_parent_arc(monkeypatch):
    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(
        campaign_builder_wizard.CampaignBuilderWizard
    )
    wizard.arcs = [
        {
            "name": "Guild War",
            "summary": "Escalation",
            "objective": "Break the syndicate",
            "status": "Planned",
            "thread": "Hidden conspiracy",
            "scenarios": ["Cold Open"],
        }
    ]
    wizard.scenario_titles = ["Cold Open"]
    wizard.form_vars = {
        "name": _FakeVar("Stormfront"),
        "genre": _FakeVar("Noir"),
        "tone": _FakeVar("Tense"),
        "status": _FakeVar("Planned"),
    }
    wizard.logline_box = _FakeTextBox("A city on the edge.")
    wizard.setting_box = _FakeTextBox("Rain-soaked towers.")
    wizard.objective_box = _FakeTextBox("Stop the syndicate war.")
    wizard.stakes_box = _FakeTextBox("The district burns.")
    wizard.themes_box = _FakeTextBox("Trust\nBetrayal")
    wizard.notes_box = _FakeTextBox("Use existing cases.")
    wizard._get_ai = lambda: object()
    refresh_calls = {"preview": 0, "review": 0}
    wizard._refresh_arcs_preview = lambda: refresh_calls.__setitem__("preview", refresh_calls["preview"] + 1)
    wizard._refresh_review = lambda: refresh_calls.__setitem__("review", refresh_calls["review"] + 1)

    class _FakeExpansionService:
        def __init__(self, ai_client):
            assert ai_client is not None

        def generate_scenarios(self, foundation, arcs):
            assert foundation["name"] == "Stormfront"
            assert arcs[0]["name"] == "Guild War"
            return {
                "arcs": [
                    {
                        "arc_name": "Guild War",
                        "scenarios": [
                            {
                                "Title": "Rainmarket Ultimatum",
                                "Summary": "",
                                "Secrets": "",
                                "Scenes": ["Scene 1", "Scene 2", "Scene 3"],
                                "Places": ["Rainmarket"],
                                "NPCs": [],
                                "Villains": ["Marshal Vey"],
                                "Creatures": [],
                                "Factions": ["Rainmarket Compact"],
                                "Objects": [],
                            },
                            {
                                "Title": "Ash Dock Reckoning",
                                "Summary": "",
                                "Secrets": "",
                                "Scenes": ["Scene 4", "Scene 5", "Scene 6"],
                                "Places": ["Ash Dock"],
                                "NPCs": [],
                                "Villains": ["Marshal Vey"],
                                "Creatures": [],
                                "Factions": ["Rainmarket Compact"],
                                "Objects": [],
                            },
                        ],
                    }
                ]
            }

    class _FakeWrapper:
        def __init__(self, entity_type):
            assert entity_type == "scenarios"

    class _FakePersistence:
        def __init__(self, scenario_wrapper):
            assert scenario_wrapper is not None

        def save_generated_arc_scenarios(self, generated_payload, arcs):
            arcs[0]["scenarios"].extend(
                [scenario["Title"] for scenario in generated_payload["arcs"][0]["scenarios"]]
            )
            return generated_payload["arcs"]

    monkeypatch.setattr(campaign_builder_wizard, "ArcScenarioExpansionService", _FakeExpansionService)
    monkeypatch.setattr(campaign_builder_wizard, "GenericModelWrapper", _FakeWrapper)
    monkeypatch.setattr(campaign_builder_wizard, "GeneratedScenarioPersistence", _FakePersistence)
    monkeypatch.setattr(campaign_builder_wizard.messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(campaign_builder_wizard.messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(campaign_builder_wizard.messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr(campaign_builder_wizard.messagebox, "showwarning", lambda *args, **kwargs: None)

    wizard._generate_scenarios_per_arc()

    assert wizard.arcs[0]["scenarios"] == [
        "Cold Open",
        "Rainmarket Ultimatum",
        "Ash Dock Reckoning",
    ]
    assert wizard.scenario_titles == [
        "Cold Open",
        "Rainmarket Ultimatum",
        "Ash Dock Reckoning",
    ]
    assert refresh_calls == {"preview": 1, "review": 1}
