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
