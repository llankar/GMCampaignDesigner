from types import SimpleNamespace

import pytest

fitz = pytest.importorskip("fitz")

from modules.pcs.character_creation.pdf_exporter import export_character_pdf


def test_export_character_pdf_creates_file(tmp_path):
    character = {
        "name": "Test",
        "player": "Unit",
        "concept": "Minimal",
        "flaw": "None",
        "group_asset": "-",
        "favorites": ["Combat"],
        "feats": [],
        "equipment": {},
        "equipment_pe": {},
        "advancements": 0,
    }
    rules_result = SimpleNamespace(
        rank_name="Novice",
        rank_index=0,
        superficial_health=3,
        skill_dice={"Combat": "d6"},
    )

    output_path = tmp_path / "character.pdf"
    result_path = export_character_pdf(character, rules_result, str(output_path))

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert result_path == str(output_path)

    with fitz.open(str(output_path)) as document:
        assert document.page_count >= 1
