from modules.scenarios.gm_table.panel_skins import (
    DESK_SPREAD_ACCENT_VARIANTS,
    readable_text_color,
    resolve_panel_chrome,
    resolve_panel_skin,
)


def test_resolve_entity_skin_accepts_canonical_display_label():
    skin = resolve_panel_skin("entity", {"entity_type": "NPCs"})

    assert skin.object_type == "Character Dossier"
    assert skin.icon == "👤"
    assert skin.show_file_tab is True


def test_resolve_entity_skin_accepts_slug_and_singular_aliases():
    assert resolve_panel_skin("entity", {"entity_type": "npc"}).icon == "👤"
    assert resolve_panel_skin("entity", {"entity_type": "information"}).icon == "🧾"
    assert resolve_panel_skin("entity", {"entity_type": "scenario"}).object_type == "Scenario Dossier"


def test_resolve_entity_skin_covers_requested_gm_table_entity_types():
    expected = {
        "NPCs": ("dossier", "Character Dossier", "👤", False, True, False),
        "PCs": ("dossier", "Character Dossier", "⭐", False, True, False),
        "Places": ("dossier", "Location Dossier", "📍", False, True, False),
        "Bases": ("dossier", "Location Dossier", "🏰", False, True, False),
        "Clues": ("paper_stack", "Evidence Card", "🔎", False, False, True),
        "Informations": ("paper_stack", "Evidence Card", "🧾", False, False, True),
        "Objects": ("binder", "Inventory Ledger", "⚖", True, False, False),
        "Creatures": ("parchment", "Bestiary Card", "🐾", False, False, True),
    }

    for entity_type, (name, object_type, icon, spine, file_tab, page_edges) in expected.items():
        skin = resolve_panel_skin("entity", {"entity_type": entity_type})

        assert skin.name == name
        assert skin.object_type == object_type
        assert skin.icon == icon
        assert skin.show_spine is spine
        assert skin.show_file_tab is file_tab
        assert skin.show_page_edges is page_edges


def test_resolve_entity_skin_accepts_requested_slug_and_singular_aliases():
    aliases = {
        "npc": "👤",
        "pc": "⭐",
        "place": "📍",
        "base": "🏰",
        "clue": "🔎",
        "info": "🧾",
        "information": "🧾",
        "object": "⚖",
        "creature": "🐾",
    }

    for alias, icon in aliases.items():
        assert resolve_panel_skin("entity", {"entity_type": alias}).icon == icon


def test_resolve_unknown_entity_skin_falls_back_to_dossier():
    skin = resolve_panel_skin("entity", {"entity_type": "Puzzles"})

    assert skin.name == "dossier"
    assert skin.object_type == "Dossier"


def test_modern_handout_skin_uses_dark_readable_surfaces_without_paper_beige():
    skin = resolve_panel_skin("handouts", {})

    assert skin.name == "paper_stack"
    assert skin.body_color == "#111927"
    assert skin.header_color == "#172235"
    assert skin.accent_color == "#22D3EE"
    assert readable_text_color(skin.body_color) == "#F8FAFC"
    assert skin.title_color == "#F8FAFC"


def test_modern_dossier_skin_avoids_old_yellow_maroon_file_chrome():
    skin = resolve_panel_skin("entity", {"entity_type": "NPCs"})

    assert skin.header_color != "#352812"
    assert skin.accent_color != "#FACC15"
    assert skin.control_bg == "#222B3D"
    assert skin.control_text == "#F8FAFC"


def test_resolved_handout_chrome_keeps_dark_content_surface_and_marker():
    skin = resolve_panel_skin("handouts", {})
    chrome = resolve_panel_chrome(skin)

    assert chrome.panel_bg == "#111927"
    assert chrome.panel_border == "#2D3A52"
    assert chrome.marker == "HANDOUT"
    assert readable_text_color(chrome.panel_bg) == "#F8FAFC"


def test_desk_spread_accent_variants_avoid_old_yellow_and_maroon_remnants():
    old_problem_colors = {
        "#FBBF24",
        "#F59E0B",
        "#FDE68A",
        "#FACC15",
        "#7C2D12",
        "#451A03",
        "#713F12",
        "#422006",
    }
    actual_colors = {
        color
        for variant in DESK_SPREAD_ACCENT_VARIANTS
        for color in (variant.top, variant.left, variant.right, variant.bottom)
    }

    assert old_problem_colors.isdisjoint(actual_colors)
