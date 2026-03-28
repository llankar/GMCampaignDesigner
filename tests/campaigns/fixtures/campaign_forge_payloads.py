from __future__ import annotations


def foundation_payload() -> dict:
    return {
        "name": "Stormfront",
        "genre": "Noir",
        "tone": "Gritty",
        "status": "Active",
        "logline": "A city on the brink.",
        "setting": "Rainmarket",
        "main_objective": "Expose the patron.",
        "stakes": "The city may collapse.",
        "themes": ["Trust", "Corruption"],
    }


def generated_arc_payload() -> dict:
    return {
        "arcs": [
            {
                "name": "Arc Alpha",
                "summary": "Street pressure rises.",
                "objective": "Find the mole.",
                "thread": "Hidden conspiracy",
                "status": "active",
                "scenarios": ["Cold Open"],
            }
        ]
    }


def generated_scenario_payload() -> dict:
    return {
        "arcs": [
            {
                "arc_name": "Arc Alpha",
                "scenarios": [
                    {
                        "Title": "Rainmarket Ultimatum",
                        "Summary": "Track the ledger courier.",
                        "Scenes": ["Stakes: lose the courier", "Corner the broker", "Escape the sweep"],
                        "Places": ["Rainmarket"],
                        "Villains": ["Marshal Vey"],
                        "Factions": ["Rainmarket Compact"],
                    },
                    {
                        "Title": "Ash Dock Reckoning",
                        "Summary": "Expose the mole.",
                        "Scenes": ["Stakes: fail and evidence burns", "Survive ambush", "Confront the mole"],
                        "Places": ["Ash Dock"],
                        "Villains": ["Marshal Vey"],
                        "Factions": ["Rainmarket Compact"],
                    },
                ],
            }
        ]
    }


def malformed_but_normalizable_scenario_payload() -> str:
    return """
    {
      "arcs": [
        {
          "arc_name": "Arc Alpha",
          "scenarios": [
            {
              "Title": "Rainmarket Ultimatum",
              "Summary": "Track the ledger courier.",
              "Scenes": ["Stakes: lose the courier", "Corner the broker", "Escape the sweep"]
            },
            {
              "Title": "Ash Dock Reckoning",
              "Summary": "Expose the mole.",
              "Scenes": ["Stakes: fail and evidence burns", "Survive ambush", "Confront the mole"]
            },
            "noise"
          ]
        },
        {
          "arc_name": "",
          "scenarios": [
            {
              "Title": "Ignored",
              "Summary": "Ignored",
              "Scenes": ["Ignored"]
            }
          ]
        },
        "junk"
      ]
    }
    """
