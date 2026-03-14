from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from modules.campaigns.services.tone_contract import CampaignToneContract


MODULE_PATH = Path("modules/ai/automation/prompt_builder.py")


def _load_prompt_builder_module():
    spec = spec_from_file_location("prompt_builder_module", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_entity_prompt_includes_tone_contract(monkeypatch):
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
