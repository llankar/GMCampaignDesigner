"""Regression tests for scene sections parser."""

from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections


def test_parse_scene_body_sections_accepts_unicode_bullet_key_beats_header():
    """Verify that parse scene body sections accepts unicode bullet key beats header."""
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
    """Verify that parse scene body sections accepts unicode bullet conflicts header."""
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
    """Verify that parse scene body sections header without bullet is unchanged."""
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
    """Verify that parse scene body sections has sections true with bulleted scene example."""
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


def test_parse_scene_body_sections_accepts_inline_header_content():
    """Verify parser keeps inline content on a same-line section header."""
    parsed = parse_scene_body_sections(
        """
• Key beats : Saut, infiltration du couloir principal, désactivation des caméras.
"""
    )

    assert parsed["has_sections"] is True
    assert parsed["sections"][0]["key"] == "key beats"
    assert parsed["sections"][0]["items"] == [
        "Saut",
        "infiltration du couloir principal",
        "désactivation des caméras.",
    ]


def test_parse_scene_body_sections_accepts_french_conflits_alias():
    """Verify parser accepts `Conflits` as alias for conflicts/obstacles."""
    parsed = parse_scene_body_sections(
        """
• Conflits / obstacles : Drones patrouilleurs, verrouillage biométrique.
"""
    )

    assert parsed["has_sections"] is True
    assert parsed["sections"][0]["key"] == "conflicts/obstacles"


def test_parse_scene_body_sections_finds_all_inline_scene_sections():
    """Verify parser extracts all known scene sections from inline bullet text."""
    parsed = parse_scene_body_sections(
        """
Les PJ doivent pénétrer dans la structure industrielle.
• Key beats : Saut, infiltration, désactivation des caméras.
• Conflicts / obstacles : verrouillage biométrique, drones patrouilleurs.
• Clues / hooks : Schéma de câblage, liste des employés.
• Transitions : Couloir de service vers salle de contrôle.
• Important locations : Hall d'entrée, salle de contrôle principale.
• Involved NPCs : Dyrektorka Katarzyna Ręzycka, gardien de sécurité.
"""
    )

    assert parsed["has_sections"] is True
    assert [section["key"] for section in parsed["sections"]] == [
        "key beats",
        "conflicts/obstacles",
        "clues/hooks",
        "transitions",
        "important locations",
        "involved npcs",
    ]
