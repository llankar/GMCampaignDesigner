"""Centralized audio controller shared across UI windows."""

from __future__ import annotations

import copy
import threading
from typing import Any, Callable, Dict, Iterable, List, Optional

from modules.audio.audio_constants import SECTION_KEYS
from modules.audio.audio_library import AudioLibrary
from modules.audio.audio_player import AudioPlayer
from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)


ControllerListener = Callable[[str, str, Dict[str, Any]], None]


class AudioController:
    """Coordinates shared audio playback state."""

    def __init__(self, library: Optional[AudioLibrary] = None) -> None:
        self.library = library or AudioLibrary()
        self._lock = threading.RLock()
        self._players: Dict[str, AudioPlayer] = {}
        self._listeners: List[ControllerListener] = []
        self._state: Dict[str, Dict[str, Any]] = {}

        for section in SECTION_KEYS:
            player = AudioPlayer()
            self._players[section] = player
            initial_state = self._initial_state(section)
            self._state[section] = initial_state
            player.add_listener(
                lambda event, payload, s=section: self._handle_player_event(s, event, payload)
            )
            # Apply saved settings to the player without re-saving them.
            player.set_volume(initial_state["volume"])
            player.set_shuffle(initial_state["shuffle"])
            player.set_loop(initial_state["loop"])

    # ------------------------------------------------------------------
    # Listener handling
    # ------------------------------------------------------------------
    def add_listener(self, callback: ControllerListener) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: ControllerListener) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _emit(self, event: str, section: str, **payload: Any) -> None:
        with self._lock:
            listeners = list(self._listeners)
        payload.setdefault("section", section)
        for callback in listeners:
            try:
                callback(section, event, payload)
            except Exception as exc:  # pragma: no cover - listener safety
                log_exception(
                    f"AudioController._emit - listener raised: {exc}",
                    func_name="AudioController._emit",
                )

    # ------------------------------------------------------------------
    # Public API used by UI components
    # ------------------------------------------------------------------
    def set_playlist(
        self,
        section: str,
        tracks: Iterable[Dict[str, Any]],
        *,
        category: Optional[str] = None,
    ) -> None:
        player = self._get_player(section)
        playlist = list(tracks)
        player.set_playlist(playlist)
        with self._lock:
            state = self._state[section]
            state["playlist"] = list(playlist)
            state["category"] = category
            state["last_error"] = ""
            if not self._track_in_playlist(state.get("current_track"), playlist):
                state["current_track"] = None
                state["is_playing"] = False
            if not self._track_in_playlist(state.get("last_track"), playlist):
                state["last_track"] = None
        self._emit("playlist_set", section, playlist=list(playlist), category=category)
        self._emit("state_changed", section, state=self.get_state(section))

    def play(
        self,
        section: str,
        *,
        start_index: Optional[int] = None,
        track_id: Optional[str] = None,
    ) -> bool:
        player = self._get_player(section)
        if track_id is not None:
            success = player.play_track_id(track_id)
        else:
            success = player.play(start_index=start_index)
        self._update_last_error(section, player.last_error if not success else "")
        if not success:
            self._emit("play_failed", section, message=player.last_error)
        return success

    def pause(self, section: str) -> None:
        player = self._get_player(section)
        player.stop()

    def stop(self, section: str) -> None:
        self.pause(section)

    def next(self, section: str) -> bool:
        player = self._get_player(section)
        success = player.next()
        self._update_last_error(section, player.last_error if not success else "")
        if not success and player.last_error:
            self._emit("navigation_failed", section, message=player.last_error)
        return success

    def previous(self, section: str) -> bool:
        player = self._get_player(section)
        success = player.previous()
        self._update_last_error(section, player.last_error if not success else "")
        if not success and player.last_error:
            self._emit("navigation_failed", section, message=player.last_error)
        return success

    def set_shuffle(self, section: str, enabled: bool) -> None:
        player = self._get_player(section)
        player.set_shuffle(bool(enabled))
        self.library.set_setting(section, "shuffle", bool(enabled))

    def set_loop(self, section: str, enabled: bool) -> None:
        player = self._get_player(section)
        player.set_loop(bool(enabled))
        self.library.set_setting(section, "loop", bool(enabled))

    def set_volume(self, section: str, value: float) -> None:
        player = self._get_player(section)
        normalized = max(0.0, min(float(value), 1.0))
        player.set_volume(normalized)
        self.library.set_setting(section, "volume", normalized)

    def get_state(self, section: str) -> Dict[str, Any]:
        with self._lock:
            state = self._state.get(section, {})
            return copy.deepcopy(state)

    def get_last_error(self, section: str) -> str:
        with self._lock:
            state = self._state.get(section, {})
            return str(state.get("last_error", ""))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _initial_state(self, section: str) -> Dict[str, Any]:
        volume = float(self.library.get_setting(section, "volume", 0.8) or 0.0)
        shuffle = bool(self.library.get_setting(section, "shuffle", False))
        loop = bool(self.library.get_setting(section, "loop", False))
        return {
            "volume": max(0.0, min(volume, 1.0)),
            "shuffle": shuffle,
            "loop": loop,
            "is_playing": False,
            "current_track": None,
            "last_track": None,
            "playlist": [],
            "category": None,
            "last_error": "",
        }

    def _get_player(self, section: str) -> AudioPlayer:
        try:
            return self._players[section]
        except KeyError as exc:
            raise KeyError(f"Unknown audio section '{section}'.") from exc

    @staticmethod
    def _track_in_playlist(track: Optional[Dict[str, Any]], playlist: List[Dict[str, Any]]) -> bool:
        if not track:
            return False
        track_id = track.get("id")
        path = track.get("path")
        for item in playlist:
            if track_id and item.get("id") == track_id:
                return True
            if path and item.get("path") == path:
                return True
        return False

    def _update_last_error(self, section: str, message: str) -> None:
        with self._lock:
            self._state[section]["last_error"] = message
        self._emit("state_changed", section, state=self.get_state(section))

    def _handle_player_event(self, section: str, event: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            state = self._state[section]
            if event == "track_started":
                state["current_track"] = payload.get("track")
                state["is_playing"] = True
                state["last_error"] = ""
                if payload.get("track"):
                    state["last_track"] = payload.get("track")
            elif event == "stopped":
                state["is_playing"] = False
                track = payload.get("track")
                if track:
                    state["last_track"] = track
            elif event == "playlist_ended":
                state["is_playing"] = False
                if state.get("current_track"):
                    state["last_track"] = state["current_track"]
            elif event == "stopped":
                state["is_playing"] = False
            elif event == "playlist_ended":
                state["is_playing"] = False
                state["current_track"] = None
            elif event == "volume_changed":
                state["volume"] = float(payload.get("value", state.get("volume", 0.0)))
            elif event == "shuffle_changed":
                state["shuffle"] = bool(payload.get("value", state.get("shuffle", False)))
            elif event == "loop_changed":
                state["loop"] = bool(payload.get("value", state.get("loop", False)))
            elif event == "error":
                state["last_error"] = str(payload.get("message", ""))
                state["is_playing"] = False
                track = payload.get("track")
                if track:
                    state["last_track"] = track
        payload = dict(payload)
        payload.setdefault("section", section)
        self._emit(event, section, payload)
        if event in {
            "track_started",
            "stopped",
            "playlist_ended",
            "volume_changed",
            "shuffle_changed",
            "loop_changed",
            "error",
        }:
            self._emit("state_changed", section, state=self.get_state(section))


_controller_singleton: Optional[AudioController] = None


def get_audio_controller() -> AudioController:
    """Return the shared :class:`AudioController` instance."""

    global _controller_singleton
    if _controller_singleton is None:
        _controller_singleton = AudioController()
    return _controller_singleton


__all__ = [
    "AudioController",
    "ControllerListener",
    "get_audio_controller",
]

