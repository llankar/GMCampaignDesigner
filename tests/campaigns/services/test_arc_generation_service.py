from modules.campaigns.services.ai import (
    ArcGenerationService,
    ArcGenerationValidationError,
    normalize_arc_generation_payload,
    parse_json_relaxed,
)


class _FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return self.response


class _FakeScenarioWrapper:
    def __init__(self, items):
        self.items = items

    def load_items(self):
        return list(self.items)


def test_parse_json_relaxed_accepts_code_fenced_payload():
    payload = parse_json_relaxed(
        """```json
        {"campaign": {"name": "Stormfront"}, "threads": [], "arcs": []}
        ```"""
    )

    assert payload["campaign"]["name"] == "Stormfront"


def test_normalize_arc_generation_payload_rejects_more_than_three_scenarios():
    payload = {
        "campaign": {"name": "Stormfront"},
        "threads": [{"name": "Main Thread", "summary": "", "arcs": ["Arc One"]}],
        "arcs": [
            {
                "name": "Arc One",
                "summary": "",
                "objective": "",
                "status": "Planned",
                "thread": "Main Thread",
                "scenarios": ["A", "B", "C", "D"],
            }
        ],
    }

    try:
        normalize_arc_generation_payload(payload, available_scenarios={"A", "B", "C", "D"})
    except ArcGenerationValidationError as exc:
        assert "3-scenario limit" in str(exc)
    else:
        raise AssertionError("Expected ArcGenerationValidationError")


def test_arc_generation_service_uses_full_scenario_catalog_and_normalizes_arcs():
    ai_client = _FakeAIClient(
        '{"campaign": {"name": "Stormfront", "summary": "", "objective": ""}, '
        '"threads": [{"name": "Conspiracy", "summary": "Escalation", "arcs": ["Arc One"]}], '
        '"arcs": [{"name": "Arc One", "summary": "Setup", "objective": "Investigate", '
        '"status": "running", "thread": "Conspiracy", "scenarios": ["Cold Open", "Hidden Ledger"]}]}'
    )
    scenario_wrapper = _FakeScenarioWrapper(
        [
            {
                "Title": "Cold Open",
                "Summary": {"text": "The crew survives the ambush."},
                "Secrets": {"text": "A mole is inside the guild."},
                "Scenes": ["Ambush", "Escape"],
            },
            {
                "Title": "Hidden Ledger",
                "Summary": {"text": "A blackmail ledger surfaces."},
                "NPCs": ["Rika Vale"],
                "Places": ["The Iron Chapel"],
            },
        ]
    )

    service = ArcGenerationService(ai_client=ai_client, scenario_wrapper=scenario_wrapper)
    result = service.generate_arcs({"name": "Stormfront", "genre": "Noir", "themes": ["Trust"]})

    assert result["arcs"] == [
        {
            "name": "Arc One",
            "summary": "Setup",
            "objective": "Investigate",
            "status": "In Progress",
            "thread": "Conspiracy",
            "scenarios": ["Cold Open", "Hidden Ledger"],
        }
    ]
    user_prompt = ai_client.messages[1]["content"]
    assert "The crew survives the ambush." in user_prompt
    assert "A mole is inside the guild." in user_prompt
    assert "Rika Vale" in user_prompt
