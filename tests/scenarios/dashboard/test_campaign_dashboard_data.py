"""Regression tests for campaign dashboard data."""

import importlib.util
from pathlib import Path

MODULE_PATH = Path("modules/scenarios/gm_screen/dashboard/campaign_dashboard_data.py")
spec = importlib.util.spec_from_file_location("scenario_dashboard_campaign_data", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
extract_campaign_fields = module.extract_campaign_fields


def test_extract_campaign_fields_hides_linked_scenarios_and_keeps_raw_arcs():
    """Verify that extract campaign fields hides linked scenarios and keeps raw arcs."""
    campaign = {
        "Name": "Dragonfall",
        "Arcs": {"text": '[{"name": "Arc One"}]'},
        "LinkedScenarios": ["Scene 1", "Scene 2"],
    }

    fields = extract_campaign_fields(campaign)

    assert "LinkedScenarios" not in {field["name"] for field in fields}

    arcs_field = next(field for field in fields if field["name"] == "Arcs")
    assert arcs_field["value"] == {"text": '[{"name": "Arc One"}]'}
