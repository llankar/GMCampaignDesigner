"""Regression tests for tone contract."""

from modules.campaigns.services.tone_contract import (
    CampaignToneContract,
    format_tone_contract_guidance,
    load_campaign_tone_contract,
)


def test_load_campaign_tone_contract_prefers_in_progress_with_constraints(monkeypatch):
    """Verify that load campaign tone contract prefers in progress with constraints."""
    campaigns = [
        {"Name": "Archive", "Status": "Planned", "Genre": "Fantasy", "Tone": "", "Setting": ""},
        {"Name": "Current", "Status": "In Progress", "Genre": "Noir", "Tone": "Bleak", "Setting": "Rain-soaked metropolis"},
    ]

    class _Wrapper:
        def __init__(self, *_args, **_kwargs):
            """Initialize the _Wrapper instance."""
            pass

        def load_items(self):
            """Load items."""
            return campaigns

    monkeypatch.setattr("modules.campaigns.services.tone_contract.GenericModelWrapper", _Wrapper)

    contract = load_campaign_tone_contract()

    assert contract == CampaignToneContract(
        campaign_name="Current",
        genre="Noir",
        tone="Bleak",
        setting="Rain-soaked metropolis",
    )


def test_load_campaign_tone_contract_returns_none_without_constraints(monkeypatch):
    """Verify that load campaign tone contract returns none without constraints."""
    campaigns = [{"Name": "Sandbox", "Status": "In Progress", "Genre": "", "Tone": "", "Setting": ""}]

    class _Wrapper:
        def __init__(self, *_args, **_kwargs):
            """Initialize the _Wrapper instance."""
            pass

        def load_items(self):
            """Load items."""
            return campaigns

    monkeypatch.setattr("modules.campaigns.services.tone_contract.GenericModelWrapper", _Wrapper)

    assert load_campaign_tone_contract() is None


def test_format_tone_contract_guidance_lists_all_constraints():
    """Verify that format tone contract guidance lists all constraints."""
    contract = CampaignToneContract(
        campaign_name="Dark Tides",
        genre="Gothic horror",
        tone="Claustrophobic and tragic",
        setting="A haunted coastal city",
    )

    guidance = format_tone_contract_guidance(contract)

    assert "Campaign tone contract" in guidance
    assert "Genre: Gothic horror" in guidance
    assert "Tone: Claustrophobic and tragic" in guidance
    assert "Setting: A haunted coastal city" in guidance
