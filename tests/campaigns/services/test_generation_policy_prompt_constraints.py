from modules.campaigns.services.ai.prompt_builders import (
    build_arc_generation_prompt,
    build_arc_scenario_expansion_prompt,
)
from modules.generic.editor.window_components.ai_scenario_generation import (
    _build_one_click_scenario_user_prompt,
)


class _FakeGenerationDefaultsService:
    def load(self):
        return {
            "main_pc_factions": ["Dawn Guard"],
            "protected_factions": ["Archivist Circle"],
            "forbidden_antagonist_factions": ["Silver Compact"],
            "allow_optional_conflicts": True,
        }


def test_arc_generation_prompt_includes_hard_constraints_from_defaults():
    prompt = build_arc_generation_prompt(
        foundation={"name": "Shattered Sky"},
        scenarios=[{"Title": "Cold Open", "Summary": "Hook"}],
        generation_defaults_service=_FakeGenerationDefaultsService(),
    )

    assert "Hard constraints:" in prompt
    assert "Never assign these factions as villains/antagonists: Silver Compact." in prompt
    assert "Treat these factions as PC allies unless explicitly marked as traitors: Dawn Guard, Archivist Circle." in prompt


def test_arc_scenario_expansion_prompt_includes_hard_constraints_from_defaults():
    prompt = build_arc_scenario_expansion_prompt(
        foundation={"name": "Shattered Sky"},
        arcs=[
            {
                "name": "Arc One",
                "summary": "Escalation",
                "objective": "Find the traitor",
                "thread": "Main",
                "scenarios": ["Cold Open"],
            }
        ],
        generation_defaults_service=_FakeGenerationDefaultsService(),
    )

    assert "Hard constraints:" in prompt
    assert "Never assign these factions as villains/antagonists: Silver Compact." in prompt
    assert "Treat these factions as PC allies unless explicitly marked as traitors: Dawn Guard, Archivist Circle." in prompt


def test_one_click_user_prompt_includes_hard_constraints_block():
    prompt = _build_one_click_scenario_user_prompt(
        theme="Noir",
        selected_npcs=["Rika Vale"],
        selected_places=["Rainmarket"],
        selected_creatures=[],
        selected_factions=["Dawn Guard"],
        selected_objects=["Ledger Fragment"],
        entities_context="Factions:\n- Dawn Guard: city defenders",
        examples_text="",
        hard_constraints_block=(
            "Hard constraints:\n"
            "- Never assign these factions as villains/antagonists: Silver Compact.\n"
            "- Treat these factions as PC allies unless explicitly marked as traitors: Dawn Guard."
        ),
    )

    assert "Hard constraints:" in prompt
    assert "Never assign these factions as villains/antagonists: Silver Compact." in prompt
    assert "Treat these factions as PC allies unless explicitly marked as traitors: Dawn Guard." in prompt
