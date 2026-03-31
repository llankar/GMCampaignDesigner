"""Utilities for audio player."""

import ctypes
import os
import platform
import random
import tempfile
import threading
import time
import uuid
import winsound
from typing import Any, Callable, Dict, List, Optional

try:
    import soundfile as sf  # type: ignore
except Exception:  # pragma: no cover - soundfile should be available, but guard anyway
    sf = None

from modules.helpers.logging_helper import (
    log_error,
    log_exception,
    log_info,
    log_warning,
    log_module_import,
)

log_module_import(__name__)

EventCallback = Callable[[str, Dict[str, Any]], None]


class AudioBackendError(Exception):
    """Raised when the underlying audio backend fails."""


class BaseAudioBackend:
    """Abstract backend interface."""

    def load(self, path: str) -> None:
        """Load the operation."""
        raise NotImplementedError

    def play(self, *, loop: bool = False) -> None:  # noqa: ARG002
        """Handle play."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop the operation."""
        raise NotImplementedError

    def is_active(self) -> bool:
        """Return whether active."""
        raise NotImplementedError

    def set_volume(self, volume: float) -> None:
        """Set volume."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the operation."""
        raise NotImplementedError

    def supports_polling(self) -> bool:
        """Handle supports polling."""
        return True


class NullAudioBackend(BaseAudioBackend):
    """Fallback backend when no audio support is available."""

    def __init__(self) -> None:
        """Initialize the NullAudioBackend instance."""
        self._volume = 1.0

    def load(self, path: str) -> None:  # pragma: no cover - diagnostics only
        """Load the operation."""
        log_warning(
            f"NullAudioBackend.load - unable to load '{path}' (no backend)",
            func_name="NullAudioBackend.load",
        )

    def play(self, *, loop: bool = False) -> None:  # noqa: ARG002  # pragma: no cover - diagnostics only
        """Handle play."""
        log_warning(
            "NullAudioBackend.play - audio playback is disabled",
            func_name="NullAudioBackend.play",
        )

    def stop(self) -> None:
        """Stop the operation."""
        # Nothing to stop
        pass

    def is_active(self) -> bool:
        """Return whether active."""
        return False

    def set_volume(self, volume: float) -> None:
        """Set volume."""
        self._volume = max(0.0, min(volume, 1.0))

    def close(self) -> None:
        """Close the operation."""
        pass

    def supports_polling(self) -> bool:
        """Handle supports polling."""
        return False


class WinMMAudioBackend(BaseAudioBackend):
    """Audio backend built on top of winsound with optional transcoding."""

    def __init__(self) -> None:
        """Initialize the WinMMAudioBackend instance."""
        if platform.system().lower() != "windows":
            raise AudioBackendError("Winsound backend requires Windows.")
        self._source_path: Optional[str] = None
        self._playback_path: Optional[str] = None
        self._converted_path: Optional[str] = None
        self._duration: float = 0.0
        self._active: bool = False
        self._timer: Optional[threading.Timer] = None
        self._volume: float = 1.0
        self._winmm = ctypes.WinDLL("winmm")
        self._wave_out_handle = ctypes.c_void_p()
        self._wave_out_set_volume = self._winmm.waveOutSetVolume
        self._wave_out_get_volume = self._winmm.waveOutGetVolume
        self._wave_out_set_volume.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self._wave_out_set_volume.restype = ctypes.c_uint
        self._wave_out_get_volume.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        self._wave_out_get_volume.restype = ctypes.c_uint
        self._initial_volume_raw: Optional[int] = self._get_device_volume_raw()

    def load(self, path: str) -> None:
        """Load the operation."""
        if not os.path.exists(path):
            raise AudioBackendError(f"File not found: {path}")
        self.stop()
        self._cleanup_temp()
        self._source_path = path
        playback_path, duration = self._prepare_playback(path)
        self._playback_path = playback_path
        self._duration = duration
        self._active = False

    def play(self, *, loop: bool = False) -> None:  # noqa: ARG002
        """Handle play."""
        if not self._playback_path or not os.path.exists(self._playback_path):
            if self._source_path:
                self.load(self._source_path)
            else:
                raise AudioBackendError("No track loaded.")
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        try:
            winsound.PlaySound(self._playback_path, flags)
        except RuntimeError as exc:
            raise AudioBackendError(f"Failed to play audio: {exc}") from exc
        self._active = True
        self._reset_timer()

    def stop(self) -> None:
        """Stop the operation."""
        self._cancel_timer()
        self._active = False
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            pass

    def is_active(self) -> bool:
        """Return whether active."""
        return self._active

    def set_volume(self, volume: float) -> None:
        """Set volume."""
        self._volume = max(0.0, min(volume, 1.0))
        if self._set_device_volume(self._volume):
            return
        log_warning(
            "WinMMAudioBackend.set_volume - failed to adjust playback volume via waveOutSetVolume",
            func_name="WinMMAudioBackend.set_volume",
        )

    def close(self) -> None:
        """Close the operation."""
        self.stop()
        self._cleanup_temp()
        self._restore_initial_volume()

    def supports_polling(self) -> bool:
        """Handle supports polling."""
        return True

    def _reset_timer(self) -> None:
        """Reset timer."""
        self._cancel_timer()
        if self._duration <= 0:
            return
        self._timer = threading.Timer(self._duration, self._on_track_finished)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self) -> None:
        """Internal helper for cancel timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _on_track_finished(self) -> None:
        """Handle track finished."""
        self._active = False

    def _prepare_playback(self, path: str) -> tuple[str, float]:
        """Internal helper for prepare playback."""
        duration = 0.0
        if sf is not None:
            # Handle the branch where sf is available.
            try:
                # Keep prepare playback resilient if this step fails.
                info = sf.info(path)
                duration = info.frames / float(info.samplerate or 1)
                if info.format and info.format.upper() == "WAV":
                    return path, duration
            except Exception as exc:
                return self._transcode_to_wav(path, fallback_error=exc)
            return self._transcode_to_wav(path)
        if path.lower().endswith('.wav'):
            duration = self._get_wav_duration(path)
            return path, duration
        return self._transcode_to_wav(path)

    def _get_wav_duration(self, path: str) -> float:
        """Return wav duration."""
        try:
            # Keep wav duration resilient if this step fails.
            import wave
            with wave.open(path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate() or 1
                return frames / float(rate)
        except Exception:
            return 0.0

    def _transcode_to_wav(self, path: str, fallback_error: Exception | None = None) -> tuple[str, float]:
        """Internal helper for transcode to wav."""
        if sf is None:
            # Handle the branch where sf is missing.
            message = "Unsupported audio format and soundfile backend unavailable."
            if fallback_error:
                message += f" Details: {fallback_error}"
            raise AudioBackendError(message)
        try:
            data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        except Exception as exc:
            raise AudioBackendError(f"Unsupported or corrupt audio file: {exc}") from exc
        tmp = tempfile.NamedTemporaryFile(prefix="gm_audio_", suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            sf.write(tmp_path, data, sample_rate, subtype="PCM_16")
        except Exception as exc:
            try:
                # Keep transcode to wav resilient if this step fails.
                os.unlink(tmp_path)
            finally:
                pass
            raise AudioBackendError(f"Failed to transcode audio: {exc}") from exc
        self._converted_path = tmp_path
        duration = data.shape[0] / float(sample_rate or 1)
        return tmp_path, duration

    def _cleanup_temp(self) -> None:
        """Internal helper for cleanup temp."""
        self._cancel_timer()
        if self._converted_path and os.path.exists(self._converted_path):
            try:
                os.unlink(self._converted_path)
            except OSError:
                pass
        self._converted_path = None
        self._playback_path = None

    def _get_device_volume_raw(self) -> Optional[int]:
        """Return device volume raw."""
        value = ctypes.c_uint()
        result = self._wave_out_get_volume(self._wave_out_handle, ctypes.byref(value))
        if result != 0:
            return None
        return int(value.value)

    def _set_device_volume(self, volume: float) -> bool:
        """Set device volume."""
        level = max(0, min(int(volume * 0xFFFF), 0xFFFF))
        packed = (level << 16) | level
        result = self._wave_out_set_volume(self._wave_out_handle, packed)
        return result == 0

    def _restore_initial_volume(self) -> None:
        """Restore initial volume."""
        if self._initial_volume_raw is None:
            return
        self._wave_out_set_volume(self._wave_out_handle, self._initial_volume_raw)


def create_backend() -> BaseAudioBackend:
    """Create backend."""
    if platform.system().lower() == "windows":
        try:
            # Keep backend resilient if this step fails.
            backend = WinMMAudioBackend()
            log_info(
                "audio_player.create_backend - using winsound backend",
                func_name="create_backend",
            )
            return backend
        except Exception as exc:  # pragma: no cover - backend selection
            log_warning(
                f"audio_player.create_backend - failed to init winsound backend: {exc}",
                func_name="create_backend",
            )
    log_warning(
        "audio_player.create_backend - falling back to null audio backend",
        func_name="create_backend",
    )
    return NullAudioBackend()


class AudioPlayer:
    """High-level playlist and playback controller."""

    def __init__(self, backend: Optional[BaseAudioBackend] = None, *, poll_interval: float = 0.5) -> None:
        """Initialize the AudioPlayer instance."""
        self._backend = backend or create_backend()
        self._lock = threading.RLock()
        self._playlist: List[Dict[str, Any]] = []
        self._current_index: int = -1
        self._shuffle: bool = False
        self._loop: bool = False
        self._continue_playback: bool = True
        self._volume: float = 0.8
        self._is_playing: bool = False
        self._stop_requested: bool = False
        self._listeners: List[EventCallback] = []
        self._poll_interval = max(0.2, float(poll_interval))
        self._supports_polling = self._backend.supports_polling()
        self._last_error: str = ""

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="AudioPlayerMonitor",
            daemon=True,
        )
        self._monitor_thread.start()

    # ------------------------------------------------------------------
    # Listener handling
    # ------------------------------------------------------------------
    def add_listener(self, callback: EventCallback) -> None:
        """Handle add listener."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: EventCallback) -> None:
        """Remove listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _emit(self, event: str, **payload: Any) -> None:
        """Internal helper for emit."""
        for callback in list(self._listeners):
            try:
                callback(event, payload)
            except Exception as exc:  # pragma: no cover - listener safety
                log_exception(
                    f"AudioPlayer._emit - listener error: {exc}",
                    func_name="AudioPlayer._emit",
                )

    # ------------------------------------------------------------------
    # Playlist control
    # ------------------------------------------------------------------
    def set_playlist(self, tracks: List[Dict[str, Any]]) -> None:
        """Set playlist."""
        with self._lock:
            # Keep this resource scoped to playlist.
            self._playlist = list(tracks)
            self._last_error = ""
            if not self._playlist:
                # Handle the branch where playlist is unavailable.
                self._current_index = -1
                self._is_playing = False
                self._backend.stop()
                self._backend.close()
            elif self._current_index >= len(self._playlist):
                self._current_index = -1

    def play(self, start_index: Optional[int] = None) -> bool:
        """Handle play."""
        with self._lock:
            # Keep this resource scoped to play.
            if not self._playlist:
                self._last_error = "Playlist is empty."
                return False
            if start_index is None:
                # Handle the branch where start index is missing.
                if self._current_index == -1:
                    if self._shuffle:
                        self._current_index = random.randrange(len(self._playlist))
                    else:
                        self._current_index = 0
                index = self._current_index
            else:
                index = max(0, min(start_index, len(self._playlist) - 1))
            return self._start_track(index)

    def play_track_id(self, track_id: str) -> bool:
        """Handle play track ID."""
        with self._lock:
            for idx, track in enumerate(self._playlist):
                if track.get("id") == track_id:
                    return self._start_track(idx)
        self._last_error = "Track not found in playlist."
        return False

    def stop(self) -> None:
        """Stop the operation."""
        with self._lock:
            # Keep this resource scoped to stop.
            if not self._is_playing:
                return
            self._stop_requested = True
            try:
                # Keep stop resilient if this step fails.
                self._backend.stop()
                self._backend.close()
            except Exception as exc:  # pragma: no cover - backend defensive
                log_warning(
                    f"AudioPlayer.stop - backend stop failed: {exc}",
                    func_name="AudioPlayer.stop",
                )
            finally:
                self._is_playing = False
                self._stop_requested = False
                self._last_error = ""
            track = self.current_track
            if track is not None:
                self._emit("stopped", track=track, index=self._current_index)

    def _start_track(self, index: int) -> bool:
        """Start track."""
        if not (0 <= index < len(self._playlist)):
            self._last_error = "Track index is out of range."
            return False
        track = self._playlist[index]
        path = track.get("path")
        if not isinstance(path, str) or not path:
            self._last_error = "Track has no valid path."
            self._emit(
                "error",
                track=track,
                message=self._last_error,
            )
            return False

        if not os.path.exists(path):
            self._last_error = f"File not found: {path}"
            self._emit(
                "error",
                track=track,
                message=self._last_error,
            )
            return False

        try:
            # Keep track resilient if this step fails.
            self._backend.load(path)
            self._backend.set_volume(self._volume)
            self._backend.play(loop=False)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            log_error(
                f"AudioPlayer._start_track - failed to play '{path}': {message}",
                func_name="AudioPlayer._start_track",
            )
            self._last_error = message
            self._emit("error", track=track, message=message)
            return False

        self._current_index = index
        self._is_playing = True
        self._stop_requested = False
        self._last_error = ""
        self._emit("track_started", track=track, index=index)
        return True

    def next(self) -> bool:
        """Handle next."""
        with self._lock:
            # Keep this resource scoped to next.
            if not self._playlist:
                self._last_error = "Playlist is empty."
                return False
            if self._shuffle and len(self._playlist) > 1:
                # Handle the branch where shuffle is set and len(_playlist) > 1.
                choices = [i for i in range(len(self._playlist)) if i != self._current_index]
                next_index = random.choice(choices)
            else:
                next_index = self._current_index + 1
                if next_index >= len(self._playlist):
                    if self._loop:
                        next_index = 0
                    else:
                        self.stop()
                        self._emit("playlist_ended")
                        self._last_error = "Reached end of playlist."
                        return False
            return self._start_track(next_index)

    def previous(self) -> bool:
        """Handle previous."""
        with self._lock:
            # Keep this resource scoped to previous.
            if not self._playlist:
                self._last_error = "Playlist is empty."
                return False
            if self._shuffle and len(self._playlist) > 1:
                # Handle the branch where shuffle is set and len(_playlist) > 1.
                choices = [i for i in range(len(self._playlist)) if i != self._current_index]
                prev_index = random.choice(choices)
            else:
                prev_index = self._current_index - 1
                if prev_index < 0:
                    if self._loop:
                        prev_index = len(self._playlist) - 1
                    else:
                        prev_index = 0
            return self._start_track(prev_index)

    def set_shuffle(self, enabled: bool) -> None:
        """Set shuffle."""
        with self._lock:
            self._shuffle = bool(enabled)
            self._emit("shuffle_changed", value=self._shuffle)

    def set_loop(self, enabled: bool) -> None:
        """Set loop."""
        with self._lock:
            self._loop = bool(enabled)
            self._emit("loop_changed", value=self._loop)

    def set_continue(self, enabled: bool) -> None:
        """Set continue."""
        with self._lock:
            # Keep this resource scoped to continue.
            value = bool(enabled)
            if self._continue_playback == value:
                return
            self._continue_playback = value
            self._emit("continue_changed", value=self._continue_playback)

    def set_volume(self, value: float) -> None:
        """Set volume."""
        with self._lock:
            # Keep this resource scoped to volume.
            self._volume = max(0.0, min(value, 1.0))
            try:
                self._backend.set_volume(self._volume)
            except Exception as exc:  # pragma: no cover - backend defensive
                log_warning(
                    f"AudioPlayer.set_volume - backend rejected volume: {exc}",
                    func_name="AudioPlayer.set_volume",
                )
            self._emit("volume_changed", value=self._volume)

    @property
    def is_playing(self) -> bool:
        """Return whether playing."""
        return self._is_playing

    @property
    def current_track(self) -> Optional[Dict[str, Any]]:
        """Handle current track."""
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index]
        return None

    @property
    def playlist(self) -> List[Dict[str, Any]]:
        """Handle playlist."""
        return list(self._playlist)

    @property
    def last_error(self) -> str:
        """Handle last error."""
        return self._last_error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _monitor_loop(self) -> None:
        """Internal helper for monitor loop."""
        while True:
            # Keep looping while True.
            time.sleep(self._poll_interval)
            if not self._supports_polling:
                continue
            with self._lock:
                # Keep this resource scoped to monitor loop.
                if not self._is_playing:
                    continue
                if self._stop_requested:
                    self._is_playing = False
                    continue
                try:
                    active = self._backend.is_active()
                except Exception as exc:  # pragma: no cover - backend defensive
                    log_warning(
                        f"AudioPlayer._monitor_loop - backend status failed: {exc}",
                        func_name="AudioPlayer._monitor_loop",
                    )
                    active = False
                if not active:
                    self._advance_after_track()

    def _advance_after_track(self) -> None:
        """Internal helper for advance after track."""
        if not self._playlist:
            self._is_playing = False
            self._current_index = -1
            self._emit("playlist_ended")
            return

        if not self._continue_playback:
            # Handle the branch where continue playback is unavailable.
            self._is_playing = False
            try:
                self._backend.stop()
                self._backend.close()
            except Exception as exc:  # pragma: no cover - backend defensive
                log_warning(
                    f"AudioPlayer._advance_after_track - backend stop failed: {exc}",
                    func_name="AudioPlayer._advance_after_track",
                )
            track = self.current_track
            if track is not None:
                self._emit("stopped", track=track, index=self._current_index)
            else:
                self._emit("playlist_ended")
            return

        if self._shuffle and len(self._playlist) > 1:
            # Handle the branch where shuffle is set and len(_playlist) > 1.
            choices = [i for i in range(len(self._playlist)) if i != self._current_index]
            next_index = random.choice(choices)
        else:
            next_index = self._current_index + 1
            if next_index >= len(self._playlist):
                if self._loop:
                    next_index = 0
                else:
                    self._is_playing = False
                    self._emit("playlist_ended")
                    return
        self._start_track(next_index)
