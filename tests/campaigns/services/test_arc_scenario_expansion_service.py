import pytest

from modules.campaigns.services.ai import (
    ArcScenarioExpansionService,
    ArcScenarioExpansionValidationError,
    GeneratedScenarioPersistence,
)


class _FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return self.response


class _FakeScenarioWrapper:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.saved_items: list[dict] = []

    def load_items(self):
        return list(self.items)

    def save_item(self, item, *, key_field=None, original_key_value=None):
        self.saved_items.append(
            {
                **dict(item),
                "_key_field": key_field,
                "_original_key_value": original_key_value,
            }
        )


def test_arc_scenario_expansion_requires_linked_scenarios():
    service = ArcScenarioExpansionService(_FakeAIClient('{"arcs": []}'))

    with pytest.raises(ArcScenarioExpansionValidationError) as exc:
        service.generate_scenarios(
            {"name": "Stormfront"},
            [
                {
                    "name": "Guild War",
                    "summary": "Escalation",
                    "objective": "Break the syndicate",
                    "thread": "Hidden conspiracy",
                    "scenarios": [],
                }
            ],
        )

    assert "at least 1 linked scenario" in str(exc.value)


def test_arc_scenario_expansion_generates_exactly_two_scenarios_per_arc():
    ai_client = _FakeAIClient(
        """
        {
          "arcs": [
            {
              "arc_name": "Guild War",
              "scenarios": [
                {
                  "Title": "Rainmarket Ultimatum",
                  "Summary": "The crew traces the conspiracy into Rainmarket.",
                  "Secrets": "A broker carries the ledger fragment.",
                  "Places": ["Rainmarket"],
                  "NPCs": ["Rika Vale"],
                  "Objects": ["Ledger Fragment"]
                },
                {
                  "Title": "Ash Dock Reckoning",
                  "Summary": "A trap at Ash Dock forces the crew to expose the mole.",
                  "Secrets": "The dockmaster answers to the same patron.",
                  "Places": ["Ash Dock"],
                  "NPCs": ["Dockmaster Neral"],
                  "Objects": []
                }
              ]
            }
          ]
        }
        """
    )
    service = ArcScenarioExpansionService(ai_client)

    result = service.generate_scenarios(
        {"name": "Stormfront", "tone": "Noir"},
        [
            {
                "name": "Guild War",
                "summary": "Street-level pressure escalates.",
                "objective": "Identify the patron behind the gang war.",
                "thread": "Hidden conspiracy",
                "scenarios": ["Cold Open"],
            }
        ],
    )

    assert len(result["arcs"]) == 1
    assert result["arcs"][0]["arc_name"] == "Guild War"
    assert len(result["arcs"][0]["scenarios"]) == 2
    assert result["arcs"][0]["scenarios"][0]["Title"] == "Rainmarket Ultimatum"
    assert "Parent arc: Guild War" in result["arcs"][0]["scenarios"][0]["Secrets"]
    assert "Hidden conspiracy" in ai_client.messages[1]["content"]


def test_generated_scenario_persistence_handles_duplicate_titles_before_save():
    wrapper = _FakeScenarioWrapper(items=[{"Title": "Rainmarket Ultimatum"}])
    persistence = GeneratedScenarioPersistence(wrapper)
    arcs = [{"name": "Guild War", "scenarios": ["Cold Open"]}]

    saved_groups = persistence.save_generated_arc_scenarios(
        {
            "arcs": [
                {
                    "arc_name": "Guild War",
                    "scenarios": [
                        {"Title": "Rainmarket Ultimatum", "Summary": "", "Secrets": "", "Places": [], "NPCs": [], "Objects": []},
                        {"Title": "Rainmarket Ultimatum", "Summary": "", "Secrets": "", "Places": [], "NPCs": [], "Objects": []},
                    ],
                }
            ]
        },
        arcs,
    )

    assert [item["Title"] for item in wrapper.saved_items] == [
        "Rainmarket Ultimatum (2)",
        "Rainmarket Ultimatum (3)",
    ]
    assert [scenario["Title"] for scenario in saved_groups[0]["scenarios"]] == [
        "Rainmarket Ultimatum (2)",
        "Rainmarket Ultimatum (3)",
    ]
