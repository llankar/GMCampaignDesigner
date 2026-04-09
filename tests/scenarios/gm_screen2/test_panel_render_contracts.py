"""Contract tests for GM Screen 2 panel widgets."""

from modules.scenarios.gm_screen2.ui.panels import (
    EntitiesPanelView,
    NotesPanelView,
    OverviewPanelView,
    QuickReferencePanelView,
    TimelinePanelView,
)


def test_panel_types_define_unique_panel_keys():
    panel_types = [
        OverviewPanelView,
        EntitiesPanelView,
        NotesPanelView,
        TimelinePanelView,
        QuickReferencePanelView,
    ]

    panel_keys = [panel_type.PANEL_KEY for panel_type in panel_types]
    assert panel_keys == ["overview", "entities", "notes", "timeline", "quick_reference"]
    assert len(panel_keys) == len(set(panel_keys))


def test_panel_types_expose_render_payload_contract():
    for panel_type in [OverviewPanelView, EntitiesPanelView, NotesPanelView, TimelinePanelView, QuickReferencePanelView]:
        assert hasattr(panel_type, "render_payload")
        assert callable(getattr(panel_type, "render_payload"))
