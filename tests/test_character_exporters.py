"""Regression tests for character exporters."""

from types import SimpleNamespace

from modules.pcs.character_creation.exporters import BACKENDS, export_character_sheet
from modules.pcs.character_creation.exporters import html_renderer


def _payload():
    """Internal helper for payload."""
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
        "advancement_choices": [
            {"type": "new_edge", "details": "Vigilance"},
            {"type": "equipment_points", "details": "Arsenal"},
        ],
    }


def _rules():
    """Internal helper for rules."""
    return SimpleNamespace(rank_name="Novice", rank_index=0, superficial_health=15, skill_dice={"Combat": "d6"}, extra_assets=["Atout: Vigilance"])


def test_render_character_sheet_html_contains_core_fields():
    """Verify that render character sheet HTML contains core fields."""
    html = html_renderer.render_character_sheet_html(_payload(), _rules())

    assert "Alya" in html
    assert "Combat" in html
    assert "■" in html
    assert "Lame vive" in html
    assert "Concept: Rogue" in html
    assert "Défaut: Impulsive" in html
    assert "Safehouse" in html
    assert "Atout: Vigilance" in html
    assert "01. +1 Atout (limité à 1 fois par Rang) — Vigilance" in html
    assert "02. Équipement : PE gagnés = 4 + Rang actuel — Arsenal" in html
    assert "<th>B. superficielles</th><th>15</th>" in html
    assert "<strong>Race</strong></div>" in html
    assert "<strong>Genre</strong></div>" in html


def test_render_character_sheet_html_supports_english_language():
    """Verify that render character sheet HTML supports english language."""
    html = html_renderer.render_character_sheet_html(_payload(), _rules(), language="en")

    assert "Character sheet" in html
    assert "Flaw: Impulsive" in html
    assert ">SKILLS<" in html
    assert "<th>Superficial wounds</th><th>15</th>" in html


def test_export_character_sheet_html_only_writes_file(tmp_path):
    """Verify that export character sheet HTML only writes file."""
    output = tmp_path / "sheet.pdf"

    path, backend = export_character_sheet(_payload(), _rules(), str(output), backend="html", export_html_only=True)

    assert backend == "html"
    assert path.endswith(".html")
    assert (tmp_path / "sheet.html").exists()


def test_export_character_sheet_forces_html_backend(tmp_path):
    """Verify that export character sheet forces HTML backend."""
    path, backend = export_character_sheet(_payload(), _rules(), str(tmp_path / "sheet.pdf"), backend="fitz")

    assert BACKENDS == ("html",)
    assert backend == "html"
    assert path.endswith("sheet.html")


def test_export_character_sheet_writes_english_html(tmp_path):
    """Verify that export character sheet writes english HTML."""
    output = tmp_path / "sheet.pdf"

    path, _ = export_character_sheet(_payload(), _rules(), str(output), language="en")

    html = (tmp_path / "sheet.html").read_text(encoding="utf-8")
    assert path.endswith("sheet.html")
    assert "Character sheet" in html


def test_render_character_sheet_html_formats_bonus_dommages_by_mode():
    """Verify that render character sheet HTML formats bonus dommages by mode."""
    payload = _payload()
    payload["feats"] = [
        {
            "name": "Frappe",
            "options": [
                "Bonus dommages : Distance, 2 pt (+99)",
                "Bonus dommages : Contact, 3 pt",
            ],
            "limitation": "",
            "prowess_points": 5,
        }
    ]

    html = html_renderer.render_character_sheet_html(payload, _rules())

    assert "Bonus dommages : Distance, 2 pt (+4)" in html
    assert "Bonus dommages : Contact, 3 pt (+7)" in html
