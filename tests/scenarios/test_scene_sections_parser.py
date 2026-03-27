from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections


def test_parse_scene_body_sections_accepts_unicode_bullet_key_beats_header():
    parsed = parse_scene_body_sections(
        """
Scene intro
• Key beats:
- Open on a tense arrival.
"""
    )

    assert parsed["has_sections"] is True
    assert parsed["sections"][0]["key"] == "key beats"
    assert parsed["sections"][0]["items"] == ["Open on a tense arrival."]


def test_parse_scene_body_sections_accepts_unicode_bullet_conflicts_header():
    parsed = parse_scene_body_sections(
        """
· Conflicts/obstacles:
- Locked gate
"""
    )

    assert parsed["has_sections"] is True
    assert parsed["sections"][0]["key"] == "conflicts/obstacles"
    assert parsed["sections"][0]["items"] == ["Locked gate"]


def test_parse_scene_body_sections_header_without_bullet_is_unchanged():
    parsed = parse_scene_body_sections(
        """
Key beats:
- Beat one
"""
    )

    assert parsed["has_sections"] is True
    assert parsed["sections"][0]["key"] == "key beats"
    assert parsed["sections"][0]["items"] == ["Beat one"]


def test_parse_scene_body_sections_has_sections_true_with_bulleted_scene_example():
    parsed = parse_scene_body_sections(
        """
A smoky tavern hums with rumors.
• Key beats:
- The ranger spots a known smuggler.
· Conflicts/obstacles:
- Two guards block the back room.
"""
    )

    assert parsed["has_sections"] is True
    assert [section["key"] for section in parsed["sections"]] == [
        "key beats",
        "conflicts/obstacles",
    ]
