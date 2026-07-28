"""Contracts for the dedicated campaign synchronization menu."""

from __future__ import annotations

from types import SimpleNamespace

from modules.ui.menu.campaign_sync_menu import build_campaign_sync_menu


def test_sync_menu_keeps_campaign_sync_actions_together() -> None:
    """Synchronization routes should not depend on a tall Campaign popup."""
    def update_settings() -> None:
        pass

    def asset_library() -> None:
        pass

    menu = build_campaign_sync_menu(
        SimpleNamespace(
            open_campaign_update_settings=update_settings,
            open_cross_campaign_asset_library=asset_library,
        )
    )

    assert menu.label == "Sync"
    assert len(menu.groups) == 1
    assert menu.groups[0].title == "Campaign Synchronization"
    assert [item.label for item in menu.groups[0].items] == [
        "Campaign Update Settings",
        "Cross-campaign Asset Library",
    ]
    assert [item.command for item in menu.groups[0].items] == [
        update_settings,
        asset_library,
    ]
