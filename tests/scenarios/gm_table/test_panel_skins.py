from modules.scenarios.gm_table.panel_skins import resolve_panel_skin


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
        "Places": ("dossier", "Location Folder", "📍", False, True, False),
        "Bases": ("dossier", "Location Folder", "🏰", False, True, False),
        "Clues": ("paper_stack", "Evidence Note", "🔎", False, False, True),
        "Informations": ("paper_stack", "Evidence Note", "🧾", False, False, True),
        "Objects": ("binder", "Inventory Ledger", "⚖", True, False, False),
        "Creatures": ("parchment", "Bestiary Page", "🐾", False, False, True),
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
