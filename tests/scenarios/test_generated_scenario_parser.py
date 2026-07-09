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


def test_italic_scene_headings_with_italic_bullet_fields_parse_scenes():
    """Italic scene labels from AI output should split into structured scenes."""
    parsed = parse_markdown_scenario(
        """
The crystal comet falls tonight.

*Scene 1:*
- *Purpose:* Discover the comet shrine before the cult arrives.
- *Location:* Starfall Meadow
- *NPCs:* Mira Dawn; Old Fen

*Scene 2:*
- *Purpose:* Negotiate with the witness who saw the impact.
- *Location:* Watchtower Ruins
- *NPCs:* Captain Rusk

*Scene 3:*
- *Purpose:* Stop the ritual under the fractured moonstone.
- *Location:* Moonstone Vault
- *NPCs:* Sable Choir; Mira Dawn
"""
    )

    scenes = parsed["Scenes"]
    assert len(scenes) == 3
    assert [scene["Title"] for scene in scenes] == ["Scene 1", "Scene 2", "Scene 3"]
    assert [scene["NPCs"] for scene in scenes] == [
        ["Mira Dawn", "Old Fen"],
        ["Captain Rusk"],
        ["Sable Choir", "Mira Dawn"],
    ]
    assert [scene["Places"] for scene in scenes] == [
        ["Starfall Meadow"],
        ["Watchtower Ruins"],
        ["Moonstone Vault"],
    ]
    assert parsed["NPCs"] == ["Mira Dawn", "Old Fen", "Captain Rusk", "Sable Choir"]
    assert parsed["Places"] == ["Starfall Meadow", "Watchtower Ruins", "Moonstone Vault"]
