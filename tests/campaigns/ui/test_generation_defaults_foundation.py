from types import SimpleNamespace
import sys


class _StubWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, _name):
        def _method(*_args, **_kwargs):
            return None

        return _method


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
        CTkCheckBox=_StubWidget,
        BooleanVar=lambda value=False: SimpleNamespace(get=lambda: value, set=lambda *_args, **_kwargs: None),
        StringVar=lambda value="": SimpleNamespace(get=lambda: value, set=lambda *_args, **_kwargs: None),
    ),
)

from modules.campaigns.ui import campaign_builder_wizard


class _FakeVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value


class _FakeTextBox:
    def __init__(self, value=""):
        self._value = value

    def get(self, *_args, **_kwargs):
        return self._value


def test_build_arc_generation_foundation_includes_generation_defaults(monkeypatch):
    monkeypatch.setattr(campaign_builder_wizard, "load_existing_entity_catalog", lambda _types: {"factions": ["Dawn Guard"]})

    wizard = campaign_builder_wizard.CampaignBuilderWizard.__new__(campaign_builder_wizard.CampaignBuilderWizard)
    wizard.form_vars = {
        "name": _FakeVar("Stormfront"),
        "genre": _FakeVar("Noir"),
        "tone": _FakeVar("Gritty"),
        "status": _FakeVar("Planned"),
    }
    wizard.logline_box = _FakeTextBox("City in chaos")
    wizard.setting_box = _FakeTextBox("Rainmarket")
    wizard.objective_box = _FakeTextBox("Keep alliances intact")
    wizard.stakes_box = _FakeTextBox("Civil war")
    wizard.themes_box = _FakeTextBox("Trust\nLoyalty")
    wizard.notes_box = _FakeTextBox("Notes")
    wizard.generation_defaults = {
        "main_pc_factions": ["Dawn Guard"],
        "protected_factions": ["Cobalt Circle"],
        "forbidden_antagonist_factions": ["Iron Banner"],
        "allow_optional_conflicts": False,
    }

    foundation = wizard._build_arc_generation_foundation()

    assert foundation["generation_defaults"]["main_pc_factions"] == ["Dawn Guard"]
    assert foundation["generation_defaults"]["allow_optional_conflicts"] is False
