from modules.campaigns.services.ai import (
    ArcGenerationService,
    ArcGenerationValidationError,
    minimum_scenarios_per_arc,
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


class _RetryingFakeAIClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages):
        self.calls.append(list(messages))
        return self.responses.pop(0)


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


def test_parse_json_relaxed_extracts_json_with_trailing_commentary():
    payload = parse_json_relaxed(
        """{"arcs": [{"arc_name": "Guild War", "scenarios": []}]}

I hope this helps."""
    )

    assert payload == {"arcs": [{"arc_name": "Guild War", "scenarios": []}]}


def test_minimum_scenarios_per_arc_scales_for_small_catalogs():
    assert minimum_scenarios_per_arc(None) == 3
    assert minimum_scenarios_per_arc(1) == 1
    assert minimum_scenarios_per_arc(2) == 2
    assert minimum_scenarios_per_arc(3) == 3
    assert minimum_scenarios_per_arc(8) == 3


def test_normalize_arc_generation_payload_rejects_arc_with_too_few_scenarios():
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
                "scenarios": ["A", "B"],
            }
        ],
    }

    try:
        normalize_arc_generation_payload(payload, available_scenarios={"A", "B", "C", "D"})
    except ArcGenerationValidationError as exc:
        assert "at least 3 connected scenarios" in str(exc)
    else:
        raise AssertionError("Expected ArcGenerationValidationError")


def test_normalize_arc_generation_payload_allows_longer_arcs_when_connected():
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

    normalized = normalize_arc_generation_payload(payload, available_scenarios={"A", "B", "C", "D"})

    assert normalized["arcs"][0]["scenarios"] == ["A", "B", "C", "D"]


def test_normalize_arc_generation_payload_resolves_title_plus_summary_aliases():
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
                "scenarios": [
                    "Cyber-attaque à Moscou : détourner un mecha de Cyberdyn",
                    "Tournée de l'Éclipse : sabotage d'un concert de rock à New York",
                    "Broken Oath",
                ],
            }
        ],
    }

    normalized = normalize_arc_generation_payload(
        payload,
        available_scenarios={
            "Cyber-attaque à Moscou": "Cyber-attaque à Moscou",
            "Cyber-attaque à Moscou: détourner un mecha de Cyberdyn": "Cyber-attaque à Moscou",
            "Tournée de l’Éclipse": "Tournée de l’Éclipse",
            "Tournée de l’Éclipse: sabotage d’un concert de rock à New York": "Tournée de l’Éclipse",
            "Broken Oath": "Broken Oath",
        },
    )

    assert normalized["arcs"][0]["scenarios"] == [
        "Cyber-attaque à Moscou",
        "Tournée de l’Éclipse",
        "Broken Oath",
    ]


def test_arc_generation_service_uses_full_scenario_catalog_and_normalizes_arcs():
    ai_client = _FakeAIClient(
        '{"campaign": {"name": "Stormfront", "summary": "", "objective": ""}, '
        '"threads": [{"name": "Conspiracy", "summary": "Escalation", "arcs": ["Arc One"]}], '
        '"arcs": [{"name": "Arc One", "summary": "Setup", "objective": "Investigate", '
        '"status": "running", "thread": "Conspiracy", "scenarios": ["Cold Open", "Hidden Ledger", "Broken Oath"]}]}'
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
            {
                "Title": "Broken Oath",
                "Summary": {"text": "An ally defects to save their family."},
                "Places": ["Old Signal Tower"],
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
            "scenarios": ["Cold Open", "Hidden Ledger", "Broken Oath"],
        }
    ]
    user_prompt = ai_client.messages[1]["content"]
    assert "The crew survives the ambush." in user_prompt
    assert "A mole is inside the guild." in user_prompt
    assert "Rika Vale" in user_prompt
    assert "connected scenarios" in user_prompt


def test_arc_generation_service_accepts_title_plus_summary_scenario_references():
    ai_client = _FakeAIClient(
        '{"campaign": {"name": "Neon Eclipse"}, "threads": [{"name": "Main Thread", "summary": "", "arcs": ["Arc One"]}], '
        '"arcs": [{"name": "Arc One", "summary": "Escalation", "objective": "Stop the conspiracy", "status": "planned", '
        '"thread": "Main Thread", "scenarios": ["Cyber-attaque à Moscou : détourner un mecha de Cyberdyn", '
        '"Tournée de l\\u2019\\u00c9clipse : sabotage d\\u2019un concert de rock à New York", "Broken Oath"]}]}'
    )
    scenario_wrapper = _FakeScenarioWrapper(
        [
            {"Title": "Cyber-attaque à Moscou", "Summary": "détourner un mecha de Cyberdyn"},
            {"Title": "Tournée de l’Éclipse", "Summary": "sabotage d’un concert de rock à New York"},
            {"Title": "Broken Oath", "Summary": "An ally defects to save their family."},
        ]
    )

    service = ArcGenerationService(ai_client=ai_client, scenario_wrapper=scenario_wrapper)
    result = service.generate_arcs({"name": "Neon Eclipse"})

    assert result["arcs"][0]["scenarios"] == [
        "Cyber-attaque à Moscou",
        "Tournée de l’Éclipse",
        "Broken Oath",
    ]


def test_arc_generation_service_retries_when_first_payload_has_single_scenario_arc():
    ai_client = _RetryingFakeAIClient(
        [
            '{"campaign": {"name": "Stormfront"}, "threads": [{"name": "Conspiracy", "summary": "", "arcs": ["Arc One"]}], '
            '"arcs": [{"name": "Arc One", "summary": "Setup", "objective": "Investigate", "status": "Planned", '
            '"thread": "Conspiracy", "scenarios": ["Cold Open"]}]}',
            '{"campaign": {"name": "Stormfront"}, "threads": [{"name": "Conspiracy", "summary": "", "arcs": ["Arc One"]}], '
            '"arcs": [{"name": "Arc One", "summary": "Setup", "objective": "Investigate", "status": "Planned", '
            '"thread": "Conspiracy", "scenarios": ["Cold Open", "Hidden Ledger", "Broken Oath"]}]}'
        ]
    )
    scenario_wrapper = _FakeScenarioWrapper(
        [
            {"Title": "Cold Open", "Summary": "The crew survives the ambush."},
            {"Title": "Hidden Ledger", "Summary": "A blackmail ledger surfaces."},
            {"Title": "Broken Oath", "Summary": "An ally defects to save their family."},
        ]
    )

    service = ArcGenerationService(ai_client=ai_client, scenario_wrapper=scenario_wrapper)
    result = service.generate_arcs({"name": "Stormfront"})

    assert result["arcs"][0]["scenarios"] == ["Cold Open", "Hidden Ledger", "Broken Oath"]
    assert len(ai_client.calls) == 2
    assert "did not satisfy the campaign-arc constraints" in ai_client.calls[1][-1]["content"]
