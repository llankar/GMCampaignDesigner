"""Helpers for GM screen command deck context and overflow cues."""

from __future__ import annotations


def resolve_now_playing_label(active_scene_key, scene_metadata, current_tab):
    """Build a short now-playing label from active scene/arc or active tab."""
    if active_scene_key:
        metadata = (scene_metadata or {}).get(active_scene_key) or {}
        scene_label = metadata.get("display_label") or metadata.get("note_title") or active_scene_key
        return f"Now Playing: 🎬 {scene_label}"
    if current_tab:
        return f"Now Playing: 🧭 {current_tab}"
    return "Now Playing: —"


def has_horizontal_overflow(content_width, viewport_width, *, threshold=8):
    """Return True when horizontal overflow is significant enough to expose controls."""
    return int(content_width or 0) > int(viewport_width or 0) + int(threshold)
