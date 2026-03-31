"""Regression tests for arc scenario expansion service."""

import pytest

from modules.campaigns.services.ai import (
    ArcScenarioExpansionService,
    ArcScenarioExpansionValidationError,
    GeneratedScenarioPersistence,
)


class _FakeAIClient:
    def __init__(self, response):
        """Initialize the _FakeAIClient instance."""
        self.response = response
        self.messages = None

    def chat(self, messages):
        """Handle chat."""
        self.messages = messages
        return self.response


class _RetryingFakeAIClient:
    def __init__(self, responses):
        """Initialize the _RetryingFakeAIClient instance."""
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages):
        """Handle chat."""
        self.calls.append(list(messages))
        return self.responses.pop(0)


class _FakeScenarioWrapper:
    def __init__(self, items=None):
        """Initialize the _FakeScenarioWrapper instance."""
        self.items = list(items or [])
        self.saved_items: list[dict] = []

    def load_items(self):
        """Load items."""
        return list(self.items)

    def save_item(self, item, *, key_field=None, original_key_value=None):
        """Save item."""
        self.saved_items.append(
            {
                **dict(item),
                "_key_field": key_field,
                "_original_key_value": original_key_value,
            }
        )

    def save_items(self, items, *, replace=True):
        """Save items."""
        self.saved_items = [dict(item) for item in items]


def test_arc_scenario_expansion_accepts_structured_playable_scenes():
    """Verify that arc scenario expansion accepts structured playable scenes."""
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
                  "Scenes": [
                    {
                      "Title": "Stakeout at Rainmarket",
                      "Objective": "Identify who receives the ledger fragment.",
                      "Setup": "The market is under curfew and entry is controlled by Marshals.",
                      "Challenge": "Get eyes on the broker without exposing the crew's presence.",
                      "Stakes": "If spotted, the ledger handoff vanishes into the alleys.",
                      "Twists": "A false courier appears to bait surveillance teams.",
                      "GMNotes": "Offer stealth, social, and bribery approaches for entry.",
                      "Outcome": "The true courier is traced to a compact safehouse.",
                      "Entities": {"NPCs": ["Rika Vale"], "Places": ["Rainmarket"], "Villains": ["Marshal Vey"], "Factions": ["Rainmarket Compact"]}
                    },
                    {
                      "Title": "Safehouse Pressure",
                      "Objective": "Extract the ledger location from compact operatives.",
                      "Setup": "The safehouse has hidden exits and panicked scouts.",
                      "Challenge": "Contain exits while negotiating or forcing cooperation.",
                      "Stakes": "Failing fast gives Vey enough time to burn evidence.",
                      "Twists": "The broker is willing to switch sides for protection.",
                      "GMNotes": "Use countdown pressure and escalating alarms.",
                      "Outcome": "The ledger route points to Ash Dock.",
                      "Entities": {"NPCs": ["Rika Vale"], "Places": ["Rainmarket"], "Villains": ["Marshal Vey"], "Factions": ["Rainmarket Compact"]}
                    },
                    {
                      "Title": "Crackdown Escape",
                      "Objective": "Get the broker out before Marshal teams close the district.",
                      "Setup": "Barricades lock down all main exits.",
                      "Challenge": "Navigate back channels while hunted by compact enforcers.",
                      "Stakes": "Capture exposes the investigation and allies.",
                      "Twists": "A compact lieutenant offers a truce in exchange for the broker.",
                      "GMNotes": "Reward improvised routes and leverage over witnesses.",
                      "Outcome": "The crew escapes with a lead on the dock conspiracy.",
                      "Entities": {"NPCs": ["Rika Vale"], "Places": ["Rainmarket"], "Villains": ["Marshal Vey"], "Factions": ["Rainmarket Compact"]}
                    }
                  ],
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

    first_scene = result["arcs"][0]["scenarios"][0]["Scenes"][0]
    assert "Objective:" in first_scene
    assert "Challenge:" in first_scene
    assert "GM Notes:" in first_scene
    assert "Villains: Marshal Vey" in first_scene


def test_arc_scenario_expansion_requires_linked_scenarios():
    """Verify that arc scenario expansion requires linked scenarios."""
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
    """Verify that arc scenario expansion generates exactly two scenarios per arc."""
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


def test_arc_scenario_expansion_retries_when_first_response_has_trailing_commentary():
    """Verify that arc scenario expansion retries when first response has trailing commentary."""
    ai_client = _RetryingFakeAIClient(
        [
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

            This extra commentary should be ignored.
            """
        ]
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

    assert result["arcs"][0]["scenarios"][0]["Title"] == "Rainmarket Ultimatum"
    assert len(ai_client.calls) == 1


def test_arc_scenario_expansion_prompt_includes_existing_entity_catalog():
    """Verify that arc scenario expansion prompt includes existing entity catalog."""
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

    service.generate_scenarios(
        {
            "name": "Stormfront",
            "tone": "Noir",
            "existing_entities": {
                "villains": ["Marshal Vey"],
                "factions": ["Rainmarket Compact"],
                "places": ["Rainmarket", "Ash Dock"],
                "npcs": ["Rika Vale", "Dockmaster Neral"],
                "creatures": ["Clockwork Hound"],
            },
        },
        [
            {
                "name": "Guild War",
                "summary": "Street-level pressure escalates.",
                "objective": "Identify the patron behind the gang war.",
                "thread": "Hidden conspiracy",
                "scenarios": ["Cold Open"],
            }
        ],
        existing_scenarios=[
            {
                "Title": "Cold Open",
                "Summary": "The opening salvo between rival crews.",
                "Scenes": [
                    {"Title": "Neon Alley Stakeout"},
                    {"Title": "The First Betrayal"},
                    "Bridge Escape",
                ],
            }
        ],
    )

    prompt = ai_client.messages[1]["content"]
    assert '"existing_entities"' in prompt
    assert "Existing scenario and scene catalog" in prompt
    assert "Marshal Vey" in prompt
    assert "Rika Vale" in prompt
    assert "Rainmarket Compact" in prompt
    assert "Cold Open" in prompt
    assert "Neon Alley Stakeout" in prompt


def test_arc_scenario_expansion_accepts_stringified_arcs_payload():
    """Verify that arc scenario expansion accepts stringified arcs payload."""
    ai_client = _FakeAIClient(
        """
        {
          "arcs": "{\"arcs\": [{\"arc_name\": \"Guild War\", \"scenarios\": [{\"Title\": \"Rainmarket Ultimatum\", \"Summary\": \"The crew traces the conspiracy into Rainmarket.\", \"Secrets\": \"A broker carries the ledger fragment.\", \"Scenes\": [\"Stake out the market\", \"Interrogate the broker\", \"Escape the crackdown\"], \"Places\": [\"Rainmarket\"], \"NPCs\": [\"Rika Vale\"], \"Villains\": [\"Marshal Vey\"], \"Creatures\": [], \"Factions\": [\"Rainmarket Compact\"], \"Objects\": [\"Ledger Fragment\"]}, {\"Title\": \"Ash Dock Reckoning\", \"Summary\": \"A trap at Ash Dock forces the crew to expose the mole.\", \"Secrets\": \"The dockmaster answers to the same patron.\", \"Scenes\": [\"Follow the dock rumor\", \"Survive the ambush\", \"Corner the mole\"], \"Places\": [\"Ash Dock\"], \"NPCs\": [\"Dockmaster Neral\"], \"Villains\": [\"Marshal Vey\"], \"Creatures\": [], \"Factions\": [\"Rainmarket Compact\"], \"Objects\": []}]}]}"
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

    assert result["arcs"][0]["arc_name"] == "Guild War"
    assert result["arcs"][0]["scenarios"][0]["Title"] == "Rainmarket Ultimatum"


def test_arc_scenario_expansion_accepts_wrapped_capitalized_arcs_payload():
    """Verify that arc scenario expansion accepts wrapped capitalized arcs payload."""
    ai_client = _FakeAIClient(
        """
        {
          "response": {
            "Arcs": [
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

    assert result["arcs"][0]["arc_name"] == "Guild War"
    assert result["arcs"][0]["scenarios"][1]["Title"] == "Ash Dock Reckoning"


def test_arc_scenario_expansion_backfills_missing_entity_creation_records():
    """Verify that arc scenario expansion backfills missing entity creation records."""
    ai_client = _FakeAIClient(
        """
        {
          "arcs": [
            {
              "arc_name": "Ghost Runners",
              "scenarios": [
                {
                  "Title": "Rescue Mission in the Mutant-Rioted Zone",
                  "Summary": "The crew pushes into a shattered district to extract a trapped asset.",
                  "Secrets": "The rescue route is being manipulated by a hostile cell.",
                  "Scenes": ["Enter the riot line", "Secure the asset", "Escape through the tunnels"],
                  "Places": ["Mutant-Rioted Zone"],
                  "NPCs": [],
                  "Villains": ["Commandant Hex"],
                  "Creatures": [],
                  "Factions": ["Nazis"],
                  "Objects": []
                },
                {
                  "Title": "Ghostline Exfiltration",
                  "Summary": "The survivors race a blockade before the trap closes for good.",
                  "Secrets": "A second team intends to erase all witnesses.",
                  "Scenes": ["Stage the convoy", "Break the blockade", "Choose who gets out"],
                  "Places": ["Transit Bunker"],
                  "NPCs": [],
                  "Villains": ["Commandant Hex"],
                  "Creatures": [],
                  "Factions": ["Nazis"],
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
        {
            "name": "Stormfront",
            "tone": "Grim",
            "existing_entities": {
                "villains": [],
                "factions": [],
                "places": [],
                "npcs": [],
                "creatures": [],
            },
        },
        [
            {
                "name": "Ghost Runners",
                "summary": "A desperate chain of extractions across occupied territory.",
                "objective": "Keep the resistance network alive.",
                "thread": "Occupied escape routes",
                "scenarios": ["Signal in the Static"],
            }
        ],
    )

    first_scenario = result["arcs"][0]["scenarios"][0]
    created_factions = first_scenario["EntityCreations"]["factions"]
    created_villains = first_scenario["EntityCreations"]["villains"]
    created_places = first_scenario["EntityCreations"]["places"]

    assert any(item["Name"] == "Nazis" for item in created_factions)
    assert any(item["Name"] == "Commandant Hex" for item in created_villains)
    assert any(item["Name"] == "Mutant-Rioted Zone" for item in created_places)


def test_generated_scenario_persistence_handles_duplicate_titles_before_save():
    """Verify that generated scenario persistence handles duplicate titles before save."""
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
    """Verify that arc scenario expansion rejects missing required links."""
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


def test_arc_scenario_expansion_auto_fixes_scene_entity_typos_from_db_catalog():
    """Verify that arc scenario expansion auto fixes scene entity typos from DB catalog."""
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
                  "Scenes": [
                    {
                      "Title": "Stakeout",
                      "Objective": "Find the broker",
                      "Setup": "The market is busy.",
                      "Challenge": "Track covert signals.",
                      "Stakes": "Lose the target.",
                      "Twists": "A decoy appears.",
                      "GMNotes": "Run as a tense skill challenge.",
                      "Outcome": "The courier route is identified.",
                      "Entities": {"NPCs": ["Rika Vaal"], "Places": ["Rainmarrket"], "Villains": ["Marshal Vey"], "Factions": ["Rainmarket Compact"]}
                    },
                    {"Title": "Pressure", "Objective": "Close in", "Setup": "Safehouse", "Challenge": "Negotiate", "Stakes": "Evidence burns", "Twists": "Double agent", "GMNotes": "Escalate clocks", "Outcome": "Dock lead", "Entities": {"Places": ["Rainmarrket"]}},
                    {"Title": "Escape", "Objective": "Get out", "Setup": "Barricades", "Challenge": "Outrun teams", "Stakes": "Capture", "Twists": "False ally", "GMNotes": "Offer risky shortcuts", "Outcome": "Crew survives", "Entities": {"NPCs": ["Rika Vaal"]}}
                  ],
                  "Places": ["Rainmarrket"],
                  "NPCs": ["Rika Vaal"],
                  "Villains": ["Marshal Vey"],
                  "Creatures": [],
                  "Factions": ["Rainmarket Compact"],
                  "Objects": []
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
        {
            "name": "Stormfront",
            "tone": "Noir",
            "existing_entities": {
                "villains": ["Marshal Vey"],
                "factions": ["Rainmarket Compact"],
                "places": ["Rainmarket", "Ash Dock"],
                "npcs": ["Rika Vale", "Dockmaster Neral"],
                "creatures": [],
            },
        },
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

    first = result["arcs"][0]["scenarios"][0]
    assert first["Places"] == ["Rainmarket"]
    assert first["NPCs"] == ["Rika Vale"]
