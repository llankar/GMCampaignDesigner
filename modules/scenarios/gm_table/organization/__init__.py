"""Organization helpers for GM Table workspaces."""

from .alignment import (
    align_geometries,
    distribute_geometries,
    eligible_panel_records,
    same_size_geometries,
    snap_geometries_to_grid,
)
from .search_index import PanelSearchResult, build_panel_search_index, filter_panel_search_index
from .sticky_notes import cluster_group_geometries, group_sticky_notes, normalize_tags, sticky_note_state

__all__ = [
    "PanelSearchResult",
    "align_geometries",
    "build_panel_search_index",
    "cluster_group_geometries",
    "distribute_geometries",
    "eligible_panel_records",
    "filter_panel_search_index",
    "group_sticky_notes",
    "normalize_tags",
    "same_size_geometries",
    "snap_geometries_to_grid",
    "sticky_note_state",
]
