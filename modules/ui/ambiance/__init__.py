"""Public API for second-screen ambiance playback."""

from __future__ import annotations

import tkinter as tk

from modules.ui.ambiance.models import AmbianceItem, AmbiancePlaylist, AmbianceState
from modules.ui.ambiance.monitor import MonitorSelectionError
from modules.ui.ambiance.player import SecondScreenAmbiancePlayer, show_single_screen_rejection

__all__ = [
    "AmbianceItem",
    "AmbiancePlaylist",
    "AmbianceState",
    "SecondScreenAmbiancePlayer",
    "start_ambiance",
    "stop_ambiance",
    "set_playlist",
]

_PLAYER_SINGLETON: SecondScreenAmbiancePlayer | None = None


def _resolve_player(root: tk.Misc) -> SecondScreenAmbiancePlayer:
    global _PLAYER_SINGLETON
    if _PLAYER_SINGLETON is None:
        _PLAYER_SINGLETON = SecondScreenAmbiancePlayer(root=root)
    return _PLAYER_SINGLETON


def set_playlist(root: tk.Misc, playlist: AmbiancePlaylist) -> SecondScreenAmbiancePlayer:
    """Set the active ambiance playlist on the singleton player."""
    player = _resolve_player(root)
    player.set_playlist(playlist)
    return player


def start_ambiance(
    root: tk.Misc,
    playlist: AmbiancePlaylist,
    *,
    allow_single_screen_fallback: bool = True,
) -> SecondScreenAmbiancePlayer:
    """Start ambiance playback with the singleton player."""
    player = _resolve_player(root)
    player.configure_single_screen_fallback(allow_single_screen_fallback)
    player.set_playlist(playlist)
    try:
        player.start()
    except MonitorSelectionError as exc:
        if not allow_single_screen_fallback:
            show_single_screen_rejection(str(exc))
        raise
    return player


def stop_ambiance() -> None:
    """Stop ambiance playback if started."""
    if _PLAYER_SINGLETON is None:
        return
    _PLAYER_SINGLETON.stop()
