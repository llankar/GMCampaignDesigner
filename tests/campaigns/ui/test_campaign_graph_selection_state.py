"""Regression tests for campaign graph selection state."""

from modules.campaigns.ui.graphical_display.services.selection_state import (
    CampaignOverviewSelectionStore,
)


class _RepositorySpy:
    def __init__(self, loaded=("", "")):
        """Initialize the _RepositorySpy instance."""
        self.loaded = loaded
        self.saved_payloads = []

    def load_overview_focus(self, campaign_name: str):
        """Load overview focus."""
        self.loaded_campaign_name = campaign_name
        return self.loaded

    def save_overview_focus(self, campaign_name: str, *, arc_name: str, scenario_title: str):
        """Save overview focus."""
        self.saved_payloads.append(
            {
                "campaign_name": campaign_name,
                "arc_name": arc_name,
                "scenario_title": scenario_title,
            }
        )


def test_load_prefers_repository_state_when_present():
    """Verify that load prefers repository state when present."""
    repository = _RepositorySpy(loaded=("Arc II", "A Quiet Night"))
    store = CampaignOverviewSelectionStore(repository)

    state = store.load({"Name": "Vampire Nights"})

    assert state.arc_name == "Arc II"
    assert state.scenario_title == "A Quiet Night"
    assert repository.loaded_campaign_name == "Vampire Nights"


def test_save_persists_using_repository_and_keeps_campaign_record_unchanged():
    """Verify that save persists using repository and keeps campaign record unchanged."""
    repository = _RepositorySpy()
    store = CampaignOverviewSelectionStore(repository)
    original = {"Name": "Vampire Nights", "Status": "In Progress"}

    updated = store.save(original, arc_name="Arc II", scenario_title="A Quiet Night")

    assert updated is original
    assert repository.saved_payloads == [
        {
            "campaign_name": "Vampire Nights",
            "arc_name": "Arc II",
            "scenario_title": "A Quiet Night",
        }
    ]


def test_save_skips_records_without_campaign_name():
    """Verify that save skips records without campaign name."""
    repository = _RepositorySpy()
    store = CampaignOverviewSelectionStore(repository)

    updated = store.save({"Status": "Draft"}, arc_name="Arc I", scenario_title="Intro")

    assert updated == {"Status": "Draft"}
    assert repository.saved_payloads == []
