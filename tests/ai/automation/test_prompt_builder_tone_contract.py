"""Regression tests for prompt builder tone contract."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from modules.campaigns.services.tone_contract import CampaignToneContract


MODULE_PATH = Path("modules/ai/automation/prompt_builder.py")


def _load_prompt_builder_module():
    """Load prompt builder module."""
    spec = spec_from_file_location("prompt_builder_module", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_entity_prompt_includes_tone_contract(monkeypatch):
    """Verify that build entity prompt includes tone contract."""
    module = _load_prompt_builder_module()

    monkeypatch.setattr(
        module,
        "load_campaign_tone_contract",
        lambda db_path=None: CampaignToneContract(
            campaign_name="Neon Ashes",
            genre="Cyberpunk",
            tone="Paranoid and gritty",
            setting="A sprawling arcology",
        ),
    )

    prompt = module.build_entity_prompt("npcs", 2, "Generate fixers", db_path="campaign.db")

    assert "Campaign tone contract (must be respected):" in prompt
    assert "Genre: Cyberpunk" in prompt
    assert "Tone: Paranoid and gritty" in prompt
    assert "Setting: A sprawling arcology" in prompt


def test_build_entity_prompt_guides_npc_description_and_atouts(monkeypatch):
    """Verify NPC prompt keeps Atouts out of Description."""
    module = _load_prompt_builder_module()
    monkeypatch.setattr(module, "load_campaign_tone_contract", lambda db_path=None: None)

    prompt = module.build_entity_prompt("npcs", 1, "Create an ally")

    assert "Description must be a physical, visual description" in prompt
    assert "Put any 'Atouts:' section in Traits instead" in prompt


def test_build_linked_entities_prompt_guides_place_description(monkeypatch):
    """Verify linked place prompt asks for image-ready physical descriptions."""
    module = _load_prompt_builder_module()
    monkeypatch.setattr(module, "load_campaign_tone_contract", lambda db_path=None: None)

    prompt = module.build_linked_entities_prompt(
        "places",
        ["Iron Chapel"],
        "Create places",
        "Parent scenario",
    )

    assert "Description must be a physical, visual description" in prompt
    assert "architecture/layout, materials, colors, lighting" in prompt
