from types import SimpleNamespace

from modules.pcs.character_creation.exporters import BACKENDS, export_character_sheet
from modules.pcs.character_creation.exporters import html_renderer


def _payload():
    return {
        "name": "Alya",
        "player": "Unit",
        "concept": "Rogue",
        "flaw": "Impulsive",
        "group_asset": "Safehouse",
        "favorites": ["Combat"],
        "feats": [{"name": "Lame vive", "options": ["+1 init"], "limitation": "1/scene"}],
        "equipment": {"weapon": "Dague", "armor": "Veste", "utility": "Outils"},
        "equipment_pe": {"weapon": 1, "armor": 1, "utility": 1},
        "advancements": 2,
    }


def _rules():
    return SimpleNamespace(rank_name="Novice", rank_index=0, superficial_health=3, skill_dice={"Combat": "d6"})


def test_render_character_sheet_html_contains_core_fields():
    html = html_renderer.render_character_sheet_html(_payload(), _rules())

    assert "Alya" in html
    assert "Combat" in html
    assert "■" in html
    assert "Lame vive" in html


def test_export_character_sheet_html_only_writes_file(tmp_path):
    output = tmp_path / "sheet.pdf"

    path, backend = export_character_sheet(_payload(), _rules(), str(output), backend="html", export_html_only=True)

    assert backend == "html"
    assert path.endswith(".html")
    assert (tmp_path / "sheet.html").exists()


def test_export_character_sheet_forces_html_backend(tmp_path):
    path, backend = export_character_sheet(_payload(), _rules(), str(tmp_path / "sheet.pdf"), backend="fitz")

    assert BACKENDS == ("html",)
    assert backend == "html"
    assert path.endswith("sheet.html")
