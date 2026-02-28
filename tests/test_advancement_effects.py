from modules.pcs.character_creation.progression.effects import _extract_matching_skills


def test_extract_matching_skills_handles_spaces_and_case() -> None:
    assert _extract_matching_skills("  combat ,   PERCEPTION ") == ["Combat", "Perception"]


def test_extract_matching_skills_supports_multiple_separators() -> None:
    assert _extract_matching_skills("Combat; Perception / Tir + Survie|Athlétisme") == [
        "Combat",
        "Perception",
        "Tir",
        "Survie",
        "Athlétisme",
    ]


def test_extract_matching_skills_supports_et_separator() -> None:
    assert _extract_matching_skills("Combat et Perception") == ["Combat", "Perception"]


def test_extract_matching_skills_supports_missing_accents() -> None:
    assert _extract_matching_skills("erudition, representation") == ["Érudition", "Représentation"]
