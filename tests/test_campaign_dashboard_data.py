from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path("modules/scenarios/gm_screen/dashboard/campaign_dashboard_data.py")
spec = spec_from_file_location("campaign_dashboard_data", MODULE_PATH)
assert spec and spec.loader
campaign_dashboard_data = module_from_spec(spec)
spec.loader.exec_module(campaign_dashboard_data)
load_campaign_entities = campaign_dashboard_data.load_campaign_entities


class _Wrapper:
    def __init__(self, items):
        self._items = items

    def load_items(self):
        return list(self._items)


def test_load_campaign_entities_reads_campaigns_wrapper_case_insensitively():
    wrappers = {
        "campaigns": _Wrapper(
            [
                {"Name": "Iron Coast"},
                {"Name": "Sable Throne"},
            ]
        )
    }

    items = load_campaign_entities(wrappers)

    assert [item["name"] for item in items] == ["Iron Coast", "Sable Throne"]


def test_load_campaign_entities_deduplicates_names_case_insensitively():
    wrappers = {
        "Campaigns": _Wrapper(
            [
                {"Name": "Iron Coast"},
                {"Name": "iron coast"},
                {"Name": "Sable Throne"},
            ]
        )
    }

    items = load_campaign_entities(wrappers)

    assert [item["name"] for item in items] == ["Iron Coast", "Sable Throne"]
