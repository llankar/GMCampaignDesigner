"""Menu definition for campaign synchronization workflows."""

from __future__ import annotations

from modules.ui.menu.menu_models import MenuCommandSpec, MenuGroupSpec, TopLevelMenuSpec


def build_campaign_sync_menu(app) -> TopLevelMenuSpec:
    """Keep synchronization actions in a short, always-visible menu."""
    return TopLevelMenuSpec(
        label="Sync",
        groups=[
            MenuGroupSpec(
                title="Campaign Synchronization",
                helper="publish, update & reuse campaign content",
                items=[
                    MenuCommandSpec(
                        "Campaign Update Settings",
                        getattr(app, "open_campaign_update_settings", None),
                        icon_key="campaign_updates",
                    ),
                    MenuCommandSpec(
                        "Cross-campaign Asset Library",
                        getattr(app, "open_cross_campaign_asset_library", None),
                        icon_key="asset_library",
                    ),
                ],
            ),
        ],
    )
