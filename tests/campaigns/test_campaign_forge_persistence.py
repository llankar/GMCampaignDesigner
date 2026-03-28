from __future__ import annotations

from modules.campaigns.services.campaign_forge_persistence import (
    CampaignForgePersistence,
    SAVE_MODE_MERGE_KEEP_EXISTING,
    SAVE_MODE_REPLACE_GENERATED_ONLY,
)
from tests.campaigns.fixtures.campaign_forge_payloads import generated_scenario_payload


class _FakeScenarioWrapper:
    def __init__(self, items=None):
        self.items = list(items or [])

    def load_items(self):
        return list(self.items)


def _arcs_with_existing_links() -> list[dict]:
    return [
        {
            "name": "Arc Alpha",
            "summary": "Street pressure rises.",
            "objective": "Find the mole.",
            "thread": "Hidden conspiracy",
            "status": "active",
            "scenarios": ["Legacy Lead"],
        }
    ]


def test_duplicate_scenario_title_collisions_are_renamed():
    wrapper = _FakeScenarioWrapper(items=[{"Title": "Rainmarket Ultimatum"}])
    persistence = CampaignForgePersistence(scenario_wrapper=wrapper)

    payload = {
        "arcs": [
            {
                "arc_name": "Arc Alpha",
                "scenarios": [
                    {
                        "Title": "Rainmarket Ultimatum",
                        "Summary": "New summary",
                        "Scenes": ["Stakes: now"],
                    },
                    {
                        "Title": "Rainmarket Ultimatum",
                        "Summary": "Second duplicate",
                        "Scenes": ["Stakes: later"],
                    },
                ],
            }
        ]
    }

    report = persistence.build_dry_run_report(
        payload,
        _arcs_with_existing_links(),
        save_mode=SAVE_MODE_MERGE_KEEP_EXISTING,
    )

    titles = [row["final_title"] for row in report["scenarios"]["items"]]
    assert titles == ["Rainmarket Ultimatum (2)", "Rainmarket Ultimatum (3)"]
    assert report["scenarios"]["summary"] == {"new": 2, "updated": 0, "skipped": 0}


def test_merge_vs_replace_behavior_for_arc_link_updates():
    wrapper = _FakeScenarioWrapper(items=[{"Title": "Legacy Lead"}])
    persistence = CampaignForgePersistence(scenario_wrapper=wrapper)

    payload = generated_scenario_payload()
    arcs_merge = _arcs_with_existing_links()
    arcs_replace = _arcs_with_existing_links()

    merge_report = persistence.build_dry_run_report(payload, arcs_merge, save_mode=SAVE_MODE_MERGE_KEEP_EXISTING)
    replace_report = persistence.build_dry_run_report(payload, arcs_replace, save_mode=SAVE_MODE_REPLACE_GENERATED_ONLY)

    merge_after = merge_report["arc_linkage"]["items"][0]["after"]
    replace_after = replace_report["arc_linkage"]["items"][0]["after"]

    assert merge_after == ["Legacy Lead", "Rainmarket Ultimatum", "Ash Dock Reckoning"]
    assert replace_after == ["Rainmarket Ultimatum", "Ash Dock Reckoning"]
