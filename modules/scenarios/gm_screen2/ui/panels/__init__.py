"""GM Screen 2 panel views."""

from modules.scenarios.gm_screen2.ui.panels.entities_panel import EntitiesPanelView
from modules.scenarios.gm_screen2.ui.panels.notes_panel import NotesPanelView
from modules.scenarios.gm_screen2.ui.panels.overview_panel import OverviewPanelView
from modules.scenarios.gm_screen2.ui.panels.quick_reference_panel import QuickReferencePanelView
from modules.scenarios.gm_screen2.ui.panels.timeline_panel import TimelinePanelView

PANEL_TYPES = {
    "overview": OverviewPanelView,
    "entities": EntitiesPanelView,
    "notes": NotesPanelView,
    "timeline": TimelinePanelView,
    "quick_reference": QuickReferencePanelView,
}

__all__ = [
    "PANEL_TYPES",
    "OverviewPanelView",
    "EntitiesPanelView",
    "NotesPanelView",
    "TimelinePanelView",
    "QuickReferencePanelView",
]
