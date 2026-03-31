"""Regression tests for campaign forge payloads."""

from __future__ import annotations


def foundation_payload() -> dict:
    """Handle foundation payload."""
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
    """Handle generated arc payload."""
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
    """Handle generated scenario payload."""
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
    """Handle malformed but normalizable scenario payload."""
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
