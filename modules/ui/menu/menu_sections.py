"""Section definitions for menu."""
from __future__ import annotations

from dataclasses import dataclass, field
from tkinter import messagebox
from typing import Callable

from modules.helpers.template_loader import NON_MANAGEABLE_ENTITY_SLUGS


@dataclass(slots=True)
class MenuCommandSpec:
    label: str
    command: Callable[[], None] | None = None
    shortcut: str = ""
    icon_key: str | None = None
    kind: str = "command"


@dataclass(slots=True)
class MenuGroupSpec:
    title: str
    helper: str
    items: list[MenuCommandSpec] = field(default_factory=list)


@dataclass(slots=True)
class TopLevelMenuSpec:
    label: str
    groups: list[MenuGroupSpec] = field(default_factory=list)


def _command(label: str, command: Callable[[], None], *, shortcut: str = "", icon_key: str | None = None) -> MenuCommandSpec:
    """Internal helper for command."""
    return MenuCommandSpec(label=label, command=command, shortcut=shortcut, icon_key=icon_key)


def _shortcut_text(shortcut: str) -> str:
    """Internal helper for shortcut text."""
    return f"\t {shortcut}" if shortcut else ""


def format_menu_label(item: MenuCommandSpec) -> str:
    """Format menu label."""
    return f"{item.label}{_shortcut_text(item.shortcut)}"


def build_menu_specs(app) -> list[TopLevelMenuSpec]:
    """Build menu specs."""
    entity_items: list[MenuCommandSpec] = []
    for slug, meta in getattr(app, "entity_definitions", {}).items():
        if slug in NON_MANAGEABLE_ENTITY_SLUGS:
            continue
        label = meta.get("label") or slug.replace("_", " ").title()
        entity_items.append(
            _command(
                f"Manage {label}",
                lambda s=slug: app.open_entity(s),
                icon_key=f"entity::{slug}",
            )
        )

    return [
        TopLevelMenuSpec(
            label="File",
            groups=[
                MenuGroupSpec(
                    title="Workspace",
                    helper="storage, backups & campaign safety",
                    items=[
                        _command("Change Database", app.change_database_storage, shortcut="F6", icon_key="change_db"),
                        _command("Create Backup", app.prompt_campaign_backup, icon_key="db_export"),
                        _command("Restore Backup", app.prompt_campaign_restore, icon_key="db_import"),
                    ],
                ),
                MenuGroupSpec(
                    title="System Setup",
                    helper="systems, schemas & shared assets",
                    items=[
                        _command("Select System", app.open_system_selector, icon_key="system_manager"),
                        _command("Set SwarmUI Path", app.select_swarmui_path, icon_key="swarm_path"),
                        _command("Customize Fields", app.open_custom_fields_editor, icon_key="customize_fields"),
                        _command("New Entity Type", app.open_new_entity_type_dialog, icon_key="new_entity_type"),
                        _command("Manage Systems", app.open_system_manager_dialog, icon_key="system_manager"),
                        _command("Cross-campaign Asset Library", app.open_cross_campaign_asset_library, icon_key="asset_library"),
                    ],
                ),
                MenuGroupSpec(
                    title="Automation",
                    helper="maintenance & assistant tooling",
                    items=[
                        _command("Auto Improve App", app.open_auto_improve_panel, icon_key="auto_improve"),
                    ],
                ),
                MenuGroupSpec(
                    title="Session Control",
                    helper="system-level actions",
                    items=[
                        _command("Quit", app.destroy, shortcut="F12"),
                    ],
                ),
            ],
        ),
        TopLevelMenuSpec(
            label="Campaign",
            groups=[
                MenuGroupSpec(
                    title="Overview",
                    helper="workshop & entity management",
                    items=[
                        _command("Campaign Workshop", app.refresh_entities),
                        *entity_items,
                    ],
                ),
                MenuGroupSpec(
                    title="Table Surfaces",
                    helper="live reference views during play",
                    items=[
                        _command("GM Screen", app.open_gm_screen, shortcut="F1", icon_key="gm_screen"),
                        _command("Campaign Overview", app.open_campaign_graph_view, icon_key="campaign_graph"),
                        _command("World Map", app.open_world_map, shortcut="F5", icon_key="world_map"),
                    ],
                ),
                MenuGroupSpec(
                    title="Story Structure",
                    helper="graphs, flow and generation aids",
                    items=[
                        _command("Character Graph", app.open_character_graph_editor, icon_key="character_graph"),
                        _command("Villain Graph", app.open_villain_graph_editor, icon_key="villain_graph"),
                        _command("Faction Graph", app.open_faction_graph_editor, icon_key="faction_graph"),
                        _command("Scenario Graph", app.open_scenario_graph_editor, icon_key="scenario_graph"),
                        _command("Scene Flow Viewer", app.open_scene_flow_viewer, icon_key="scene_flow_viewer"),
                        _command("Create Random Table", app.open_random_table_editor, icon_key="create_random_table"),
                    ],
                ),
            ],
        ),
        TopLevelMenuSpec(
            label="GM Tools",
            groups=[
                MenuGroupSpec(
                    title="Scenario Design",
                    helper="build, generate and export sessions",
                    items=[
                        _command("Generate Scenario", app.open_scenario_generator, icon_key="generate_scenario"),
                        _command("Scenario Builder", app.open_scenario_builder, shortcut="F4", icon_key="scenario_builder"),
                        _command("Campaign Builder", app.open_campaign_builder, shortcut="F9", icon_key="campaign_builder"),
                        _command("Export Scenarios", app.preview_and_export_scenarios, icon_key="export_scenarios"),
                        _command("Export Campaign Dossier", app.open_campaign_dossier_exporter, icon_key="export_campaign_dossier"),
                    ],
                ),
                MenuGroupSpec(
                    title="Imports & Media",
                    helper="bring content into the campaign quickly",
                    items=[
                        _command("Import Scenario", app.open_scenario_importer, icon_key="import_scenario"),
                        _command("Import Creatures (PDF)", app.open_creature_importer, icon_key="import_creatures_pdf"),
                        _command("Import Objects (PDF)", app.open_object_importer, icon_key="import_objects_pdf"),
                        _command("Generate Portraits", app.generate_missing_portraits, icon_key="generate_portraits"),
                        _command("Import Portraits from Folder", app.import_portraits_from_directory, icon_key="import_portraits"),
                        _command("Import Image Directories…", app.open_image_directory_importer),
                        _command("Open Image Library", app.open_image_library_browser),
                    ],
                ),
                MenuGroupSpec(
                    title="Live Table Tools",
                    helper="running-session utilities and overlays",
                    items=[
                        _command("Map Tool", app.map_tool, shortcut="F2", icon_key="map_tool"),
                        _command("Whiteboard", app.open_whiteboard, shortcut="F3", icon_key="whiteboard"),
                        _command("Dice", app.open_dice_roller, shortcut="F8", icon_key="dice_roller"),
                        _command("Sound & Music", app.open_sound_manager, shortcut="F7", icon_key="audio_controls"),
                        _command("Session Timers", app.open_timer_window, icon_key="session_timers"),
                        _command("Character Creation", app.open_character_creation),
                    ],
                ),
            ],
        ),
        TopLevelMenuSpec(
            label="View",
            groups=[
                MenuGroupSpec(
                    title="Panels",
                    helper="toggle persistent utility bars",
                    items=[
                        _command("Show Audio Bar", app.open_audio_bar, icon_key="audio_controls"),
                        _command("Show Dice Bar", app.open_dice_bar, icon_key="dice_bar"),
                    ],
                ),
            ],
        ),
        TopLevelMenuSpec(
            label="Help",
            groups=[
                MenuGroupSpec(
                    title="Reference",
                    helper="keyboard shortcuts and guidance",
                    items=[
                        _command(
                            "Shortcuts",
                            lambda: messagebox.showinfo(
                                "Keyboard Shortcuts",
                                "F1: GM Screen\n"
                                "F2: Map Tool\n"
                                "F3: Whiteboard\n"
                                "F4: Scenario Builder\n"
                                "F5: World Map\n"
                                "F6: Change Database\n"
                                "F7: Sound & Music\n"
                                "F8: Dice\n"
                                "F9: Campaign Builder\n"
                                "F12: Quit",
                            ),
                        ),
                    ],
                ),
            ],
        ),
    ]
