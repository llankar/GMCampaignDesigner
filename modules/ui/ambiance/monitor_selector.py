"""Monitor index normalization and fallback policy for ambiance playback."""

from __future__ import annotations


def normalize_target_monitor(requested_index: int | None, monitor_count: int) -> tuple[int, str | None]:
    """Resolve requested monitor index to a safe target and optional user warning."""
    if monitor_count <= 0:
        return 0, "No monitor detected, using primary monitor."

    if requested_index is None:
        return (1, None) if monitor_count > 1 else (0, None)

    try:
        index = int(requested_index)
    except Exception:
        return 0, "Invalid monitor index, using primary monitor."

    if index < 0:
        return 0, "Invalid monitor index, using primary monitor."

    if index == 1 and monitor_count < 2:
        return 0, "Secondary monitor not detected, using primary monitor."

    if index >= monitor_count:
        return 0, "Invalid monitor index, using primary monitor."

    return index, None
