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
