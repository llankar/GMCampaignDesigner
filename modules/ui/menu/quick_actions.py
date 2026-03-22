from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class QuickActionSpec:
    text: str
    command: Callable[[], None]
    icon_key: str | None = None
    tooltip: str = ""
    style: str = "primary"


PRIMARY_ACTIONS = (
    QuickActionSpec("GM Screen", lambda app: app.open_gm_screen(), "gm_screen", "Open the GM reference screen"),
    QuickActionSpec("Scenario", lambda app: app.open_scenario_builder(), "scenario_builder", "Launch the scenario builder"),
    QuickActionSpec("Campaign", lambda app: app.open_campaign_builder(), "campaign_builder", "Launch the campaign builder"),
    QuickActionSpec("World Map", lambda app: app.open_world_map(), "world_map", "Jump to the world map"),
    QuickActionSpec("MapTool", lambda app: app.map_tool(), "map_tool", "Jump to the map tool"),
    QuickActionSpec("Dice", lambda app: app.open_dice_roller(), "dice_roller", "Open the dice roller"),
    QuickActionSpec("Audio", lambda app: app.open_sound_manager(), "audio_controls", "Control sound and music"),
)

SYSTEM_ACTIONS = (
    QuickActionSpec("Backup", lambda app: app.prompt_campaign_backup(), "db_export", "Create a campaign backup", "system"),
    QuickActionSpec("DB", lambda app: app.change_database_storage(), "change_db", "Switch the active database", "system"),
)


def _bind_actions(app, items: tuple[QuickActionSpec, ...]) -> list[QuickActionSpec]:
    bound: list[QuickActionSpec] = []
    for item in items:
        bound.append(
            QuickActionSpec(
                text=item.text,
                command=lambda func=item.command: func(app),
                icon_key=item.icon_key,
                tooltip=item.tooltip,
                style=item.style,
            )
        )
    return bound


def build_primary_quick_actions(app) -> list[QuickActionSpec]:
    return _bind_actions(app, PRIMARY_ACTIONS)


def build_system_quick_actions(app) -> list[QuickActionSpec]:
    return _bind_actions(app, SYSTEM_ACTIONS)
