"""Regression tests for image library menu commands."""

from __future__ import annotations

from types import SimpleNamespace

from modules.ui.menu.menu_sections import build_menu_specs


def test_menu_sections_expose_image_library_commands() -> None:
    """GM tools imports section should expose shared image asset actions."""
    app = SimpleNamespace(
        entity_definitions={},
        change_database_storage=lambda: None,
        prompt_campaign_backup=lambda: None,
        prompt_campaign_restore=lambda: None,
        open_system_selector=lambda: None,
        select_swarmui_path=lambda: None,
        open_custom_fields_editor=lambda: None,
        open_new_entity_type_dialog=lambda: None,
        open_system_manager_dialog=lambda: None,
        open_cross_campaign_asset_library=lambda: None,
        open_auto_improve_panel=lambda: None,
        destroy=lambda: None,
        refresh_entities=lambda: None,
        open_gm_screen=lambda: None,
        open_campaign_graph_view=lambda: None,
        open_world_map=lambda: None,
        open_character_graph_editor=lambda: None,
        open_villain_graph_editor=lambda: None,
        open_faction_graph_editor=lambda: None,
        open_scenario_graph_editor=lambda: None,
        open_scene_flow_viewer=lambda: None,
        open_random_table_editor=lambda: None,
        open_scenario_generator=lambda: None,
        open_scenario_builder=lambda: None,
        open_campaign_builder=lambda: None,
        preview_and_export_scenarios=lambda: None,
        open_campaign_dossier_exporter=lambda: None,
        open_scenario_importer=lambda: None,
        open_creature_importer=lambda: None,
        open_object_importer=lambda: None,
        generate_missing_portraits=lambda: None,
        import_portraits_from_directory=lambda: None,
        open_image_directory_importer=lambda: None,
        open_image_library_browser=lambda: None,
        map_tool=lambda: None,
        open_whiteboard=lambda: None,
        open_dice_roller=lambda: None,
        open_sound_manager=lambda: None,
        open_timer_window=lambda: None,
        open_character_creation=lambda: None,
        open_audio_bar=lambda: None,
        open_dice_bar=lambda: None,
    )

    specs = build_menu_specs(app)
    gm_tools = next(menu for menu in specs if menu.label == "GM Tools")
    imports_group = next(group for group in gm_tools.groups if group.title == "Imports & Media")
    labels = [item.label for item in imports_group.items]

    assert "Import Image Directories…" in labels
    assert "Open Image Library" in labels


def test_campaign_menu_hides_internal_manage_entity_entries() -> None:
    """Campaign overview should not expose internal entity management commands."""
    app = SimpleNamespace(
        entity_definitions={
            "events": {"label": "Events"},
            "image_assets": {"label": "Image Assets"},
            "npcs": {"label": "NPCs"},
        },
        open_entity=lambda _slug: None,
        change_database_storage=lambda: None,
        prompt_campaign_backup=lambda: None,
        prompt_campaign_restore=lambda: None,
        open_system_selector=lambda: None,
        select_swarmui_path=lambda: None,
        open_custom_fields_editor=lambda: None,
        open_new_entity_type_dialog=lambda: None,
        open_system_manager_dialog=lambda: None,
        open_cross_campaign_asset_library=lambda: None,
        open_auto_improve_panel=lambda: None,
        destroy=lambda: None,
        refresh_entities=lambda: None,
        open_gm_screen=lambda: None,
        open_campaign_graph_view=lambda: None,
        open_world_map=lambda: None,
        open_character_graph_editor=lambda: None,
        open_villain_graph_editor=lambda: None,
        open_faction_graph_editor=lambda: None,
        open_scenario_graph_editor=lambda: None,
        open_scene_flow_viewer=lambda: None,
        open_random_table_editor=lambda: None,
        open_scenario_generator=lambda: None,
        open_scenario_builder=lambda: None,
        open_campaign_builder=lambda: None,
        preview_and_export_scenarios=lambda: None,
        open_campaign_dossier_exporter=lambda: None,
        open_scenario_importer=lambda: None,
        open_creature_importer=lambda: None,
        open_object_importer=lambda: None,
        generate_missing_portraits=lambda: None,
        import_portraits_from_directory=lambda: None,
        open_image_directory_importer=lambda: None,
        open_image_library_browser=lambda: None,
        map_tool=lambda: None,
        open_whiteboard=lambda: None,
        open_dice_roller=lambda: None,
        open_sound_manager=lambda: None,
        open_timer_window=lambda: None,
        open_character_creation=lambda: None,
        open_audio_bar=lambda: None,
        open_dice_bar=lambda: None,
    )

    specs = build_menu_specs(app)
    campaign_menu = next(menu for menu in specs if menu.label == "Campaign")
    overview_group = next(group for group in campaign_menu.groups if group.title == "Overview")
    labels = [item.label for item in overview_group.items]

    assert "Manage NPCs" in labels
    assert "Manage Events" not in labels
    assert "Manage Image Assets" not in labels
