"""Playlist mutation helpers for GM Table ambiance page."""

from __future__ import annotations

from dataclasses import dataclass

from modules.ui.ambiance.library.models import WallpaperLibraryItem


@dataclass(frozen=True, slots=True)
class AddAllResult:
    """Result metadata for batch playlist append actions."""

    added_count: int
    already_present_count: int


def add_missing_items_to_playlist(
    *,
    playlist_entries: list[dict],
    library_items: list[WallpaperLibraryItem],
    default_duration: float,
) -> AddAllResult:
    """Append items to playlist while keeping order and preventing duplicates."""
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for entry in playlist_entries:
        item_id = str((entry or {}).get("id") or "").strip()
        if item_id:
            seen_ids.add(item_id)
        raw_path = str((entry or {}).get("path") or "").strip()
        if raw_path:
            seen_paths.add(raw_path)

    added = 0
    skipped = 0
    for item in library_items:
        path_key = str(item.relative_path or "").strip()
        if item.id in seen_ids or (path_key and path_key in seen_paths):
            skipped += 1
            continue
        playlist_entries.append({"id": item.id, "path": path_key, "duration": float(default_duration)})
        seen_ids.add(item.id)
        if path_key:
            seen_paths.add(path_key)
        added += 1

    return AddAllResult(added_count=added, already_present_count=skipped)
