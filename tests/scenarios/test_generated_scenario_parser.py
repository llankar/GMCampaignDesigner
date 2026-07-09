"""Regression tests for generated scenario markdown parsing."""

from modules.scenarios.generated_scenario_parser import parse_markdown_scenario


def test_bold_markdown_entity_json_sections_parse_structured_records_only():
    """Bold entity labels should extract fenced JSON without prose token leakage."""
    parsed = parse_markdown_scenario(
        """
The masquerade is about to collapse.

**NPCs:**   
```json
[
  {
    "Name": "Lysa Vale",
    "Role": "Disgraced heir",
    "Motivation": "Expose the masked blackmailer."
  },
  {
    "Name": "Darius Kessler",
    "Role": "House guard",
    "Motivation": "Keep the gala from turning violent."
  }
]
```

**Locations:**   
```json
[
  {
    "Name": "Moonlit Ballroom",
    "Description": "A mirrored hall full of nervous nobles."
  },
  {
    "Name": "Servants' Stair",
    "Description": "A narrow route used for secret meetings."
  }
]
```
"""
    )

    assert parsed["NPCs"] == [
        {
            "Name": "Lysa Vale",
            "Role": "Disgraced heir",
            "Motivation": "Expose the masked blackmailer.",
        },
        {
            "Name": "Darius Kessler",
            "Role": "House guard",
            "Motivation": "Keep the gala from turning violent.",
        },
    ]
    assert parsed["Places"] == [
        {
            "Name": "Moonlit Ballroom",
            "Description": "A mirrored hall full of nervous nobles.",
        },
        {
            "Name": "Servants' Stair",
            "Description": "A narrow route used for secret meetings.",
        },
    ]

    assert [npc["Name"] for npc in parsed["NPCs"]] == ["Lysa Vale", "Darius Kessler"]
    assert all(isinstance(npc, dict) for npc in parsed["NPCs"])

    npc_values = [str(value) for npc in parsed["NPCs"] for value in npc.values()]
    leaked_tokens = ["```json", "[", "{", "}", '"Name": "Lysa Vale"']
    assert not any(token in value for token in leaked_tokens for value in npc_values)
