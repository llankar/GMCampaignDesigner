"""Services for GM Screen handouts collection."""

from __future__ import annotations

from dataclasses import dataclass

from modules.scenarios.gm_table.handouts.service import collect_scenario_handouts


@dataclass(frozen=True)
class GMScreenHandoutItem:
    """Resolved handout descriptor used by the GM Screen handouts panel."""

    id: str
    title: str
    path: str
    kind: str
    subtitle: str | None = None


def collect_gm_screen_handouts(
    scenario_item: dict,
    wrappers: dict[str, object],
    map_wrapper: object,
) -> list[GMScreenHandoutItem]:
    """Collect scenario-linked portraits and maps for the GM Screen handouts tab."""

    items = collect_scenario_handouts(scenario_item, wrappers, map_wrapper)
    return [
        GMScreenHandoutItem(
            id=item.id,
            title=item.title,
            path=item.path,
            kind=item.kind,
            subtitle=item.subtitle,
        )
        for item in items
    ]
