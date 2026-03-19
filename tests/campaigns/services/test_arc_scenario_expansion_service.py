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

    def save_items(self, items, *, replace=True):
        self.saved_items = [dict(item) for item in items]


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
                  "Scenes": ["Stake out the market", "Interrogate the broker", "Escape the crackdown"],
                  "Places": ["Rainmarket"],
                  "NPCs": ["Rika Vale"],
                  "Villains": ["Marshal Vey"],
                  "Creatures": [],
                  "Factions": ["Rainmarket Compact"],
                  "Objects": ["Ledger Fragment"]
                },
                {
                  "Title": "Ash Dock Reckoning",
                  "Summary": "A trap at Ash Dock forces the crew to expose the mole.",
                  "Secrets": "The dockmaster answers to the same patron.",
                  "Scenes": ["Follow the dock rumor", "Survive the ambush", "Corner the mole"],
                  "Places": ["Ash Dock"],
                  "NPCs": ["Dockmaster Neral"],
                  "Villains": ["Marshal Vey"],
                  "Creatures": [],
                  "Factions": ["Rainmarket Compact"],
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
    assert result["arcs"][0]["scenarios"][0]["Scenes"] == [
        "Stake out the market",
        "Interrogate the broker",
        "Escape the crackdown",
    ]
    assert result["arcs"][0]["scenarios"][0]["Villains"] == ["Marshal Vey"]
    assert "Hidden conspiracy" in ai_client.messages[1]["content"]


def test_generated_scenario_persistence_handles_duplicate_titles_before_save():
    wrapper = _FakeScenarioWrapper(items=[{"Title": "Rainmarket Ultimatum"}])
    persistence = GeneratedScenarioPersistence(
        wrapper,
        entity_wrappers={
            "villains": _FakeScenarioWrapper(),
            "factions": _FakeScenarioWrapper(),
            "places": _FakeScenarioWrapper(),
            "npcs": _FakeScenarioWrapper(),
            "creatures": _FakeScenarioWrapper(),
        },
    )
    arcs = [{"name": "Guild War", "scenarios": ["Cold Open"]}]

    saved_groups = persistence.save_generated_arc_scenarios(
        {
            "arcs": [
                {
                    "arc_name": "Guild War",
                    "scenarios": [
                        {
                            "Title": "Rainmarket Ultimatum",
                            "Summary": "",
                            "Secrets": "",
                            "Scenes": ["A", "B", "C"],
                            "Places": ["Rainmarket"],
                            "NPCs": [],
                            "Villains": ["Marshal Vey"],
                            "Creatures": [],
                            "Factions": ["Rainmarket Compact"],
                            "Objects": [],
                            "EntityCreations": {
                                "villains": [{"Name": "Marshal Vey", "Description": "A relentless enforcer."}],
                                "factions": [{"Name": "Rainmarket Compact", "Description": "Market fixers."}],
                                "places": [{"Name": "Rainmarket", "Description": "A covered bazaar."}],
                                "npcs": [],
                                "creatures": [],
                            },
                        },
                        {
                            "Title": "Rainmarket Ultimatum",
                            "Summary": "",
                            "Secrets": "",
                            "Scenes": ["D", "E", "F"],
                            "Places": ["Rainmarket"],
                            "NPCs": [],
                            "Villains": ["Marshal Vey"],
                            "Creatures": [],
                            "Factions": ["Rainmarket Compact"],
                            "Objects": [],
                        },
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
    assert persistence.entity_wrappers["villains"].saved_items[0]["Name"] == "Marshal Vey"
    assert persistence.entity_wrappers["factions"].saved_items[0]["Name"] == "Rainmarket Compact"
    assert persistence.entity_wrappers["places"].saved_items[0]["Name"] == "Rainmarket"


def test_arc_scenario_expansion_rejects_missing_required_links():
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
                  "Scenes": ["Stake out the market", "Pressure the broker", "Evade the crackdown"],
                  "Places": ["Rainmarket"],
                  "NPCs": [],
                  "Villains": [],
                  "Creatures": [],
                  "Factions": [],
                  "Objects": []
                },
                {
                  "Title": "Ash Dock Reckoning",
                  "Summary": "A trap at Ash Dock forces the crew to expose the mole.",
                  "Secrets": "The dockmaster answers to the same patron.",
                  "Scenes": ["Follow the dock rumor", "Survive the ambush", "Corner the mole"],
                  "Places": ["Ash Dock"],
                  "NPCs": [],
                  "Villains": ["Marshal Vey"],
                  "Creatures": [],
                  "Factions": ["Rainmarket Compact"],
                  "Objects": []
                }
              ]
            }
          ]
        }
        """
    )
    service = ArcScenarioExpansionService(ai_client)

    with pytest.raises(ArcScenarioExpansionValidationError) as exc:
        service.generate_scenarios(
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

    assert "at least 1 villain" in str(exc.value)
