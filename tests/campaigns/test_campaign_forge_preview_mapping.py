from __future__ import annotations

from modules.campaigns.ui.campaign_forge_preview.models import CampaignForgeScenarioPreview
from modules.campaigns.ui.campaign_forge_preview_dialog import CampaignForgePreviewDialog


class _FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_build_arc_previews_maps_metadata_and_scenario_warnings():
    dialog = CampaignForgePreviewDialog.__new__(CampaignForgePreviewDialog)
    dialog._validation = type(
        "Validation",
        (),
        {
            "scenario_warnings": {
                ("arc alpha", "rainmarket ultimatum"): ["weak links", "empty stakes"],
            }
        },
    )()

    generated_payload = {
        "arcs": [
            {
                "arc_name": "Arc Alpha",
                "scenarios": [
                    {
                        "Title": "Rainmarket Ultimatum",
                        "Summary": "Track the courier",
                    }
                ],
            }
        ]
    }
    arc_metadata = {
        "arc alpha": {
            "objective": "Find the mole",
            "thread": "Conspiracy",
            "status": "active",
        }
    }

    previews = dialog._build_arc_previews(generated_payload, arc_metadata)

    assert len(previews) == 1
    assert previews[0].name == "Arc Alpha"
    assert previews[0].objective == "Find the mole"
    assert previews[0].scenarios[0].warnings == ["weak links", "empty stakes"]


def test_accept_supports_partial_selection_from_preview_dialog():
    dialog = CampaignForgePreviewDialog.__new__(CampaignForgePreviewDialog)
    dialog._generated_payload = {
        "arcs": [
            {
                "arc_name": "Arc Alpha",
                "scenarios": [
                    {"Title": "Rainmarket Ultimatum", "Summary": "A"},
                    {"Title": "Ash Dock Reckoning", "Summary": "B"},
                ],
            }
        ],
        "meta": {"campaign": "Stormfront"},
    }

    dialog._arc_rows = [
        {
            "arc_var": _FakeVar(True),
            "arc": type("Arc", (), {"name": "Arc Alpha"})(),
            "scenario_rows": [
                {
                    "scenario_var": _FakeVar(True),
                    "scenario": CampaignForgeScenarioPreview(
                        arc_name="Arc Alpha",
                        title="Rainmarket Ultimatum",
                        summary="A",
                    ),
                },
                {
                    "scenario_var": _FakeVar(False),
                    "scenario": CampaignForgeScenarioPreview(
                        arc_name="Arc Alpha",
                        title="Ash Dock Reckoning",
                        summary="B",
                    ),
                },
            ],
        }
    ]

    destroyed = {"called": False}
    dialog.destroy = lambda: destroyed.__setitem__("called", True)

    dialog._accept()

    assert destroyed["called"] is True
    assert dialog.result == {
        "arcs": [
            {
                "arc_name": "Arc Alpha",
                "scenarios": [{"Title": "Rainmarket Ultimatum", "Summary": "A"}],
            }
        ],
        "meta": {"campaign": "Stormfront"},
    }
