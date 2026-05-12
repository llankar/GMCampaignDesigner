"""Small helpers for campaign graph payload caches."""

from __future__ import annotations

from typing import Any

from modules.campaigns.ui.graphical_display.data import CampaignGraphPayload


def clear_campaign_graph_caches(
    payload_cache: dict[str, CampaignGraphPayload],
    scenario_items_cache: dict[str, list[dict[str, Any]]],
) -> None:
    """Invalidate cached campaign graph payloads and their scenario rows."""
    payload_cache.clear()
    scenario_items_cache.clear()


def cache_campaign_graph_payload(
    campaign_name: str,
    payload: CampaignGraphPayload | None,
    scenario_items: list[dict[str, Any]],
    payload_cache: dict[str, CampaignGraphPayload],
    scenario_items_cache: dict[str, list[dict[str, Any]]],
) -> None:
    """Store a graph payload and scenario rows for a campaign selection."""
    if payload is None:
        payload_cache.pop(campaign_name, None)
        scenario_items_cache.pop(campaign_name, None)
        return

    payload_cache[campaign_name] = payload
    scenario_items_cache[campaign_name] = list(scenario_items)
