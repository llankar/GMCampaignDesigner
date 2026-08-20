"""Utility helpers for displaying videos on the secondary monitor."""

from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass

import customtkinter as ctk
from PIL import Image, ImageTk

try:
    import av  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    av = None

from modules.ui.image_viewer import _get_monitors
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_module_import,
)

log_module_import(__name__)

_active_player = None

_RESAMPLING = getattr(Image, "Resampling", Image)
_RESAMPLE_MODE = getattr(_RESAMPLING, "LANCZOS", Image.LANCZOS)


@dataclass
class _MonitorBounds:
    x: int
    y: int
    width: int
    height: int


class _SecondScreenVideoPlayer:
    """Simple video player that renders frames inside a fullscreen CTk window."""

    def __init__(self, video_path: str, title: str | None = None, *, loop: bool = True) -> None:
        """Initialize the _SecondScreenVideoPlayer instance."""
        if av is None:
            raise RuntimeError("PyAV is required to play video files.")

        self._container = self._open_container(video_path)
        self._loop = loop
        self._stream = self._get_video_stream()
        self._frame_iterator = self._container.decode(self._stream)
        self._frame_delay = self._calculate_frame_delay()
        self._after_ids: set[str] = set()
        self._stopped = False

        monitor = self._select_monitor()
        self.window = self._build_window(video_path, title, monitor)
        self._image_label = tk.Label(self.window, bg="black")
        self._image_label.pack(fill="both", expand=True)

        self.window.bind("<Escape>", self.close)
        self.window.bind("<Button-1>", self.close)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        # Kick off playback after the window has had a chance to layout.
        self._schedule(0, self._render_next_frame)

    def _open_container(self, path: str):
        """Open container."""
        try:
            return av.open(path)
        except Exception as exc:  # pragma: no cover - depends on runtime files
            raise RuntimeError(f"Unable to open video file: {exc}") from exc

    def _get_video_stream(self):
        """Return video stream."""
        stream = next((s for s in self._container.streams if s.type == "video"), None)
        if stream is None:
            self._container.close()
            raise RuntimeError("The selected file does not contain a video stream.")
        stream.thread_type = "AUTO"
        return stream

    def _calculate_frame_delay(self) -> int:
        """Internal helper for calculate frame delay."""
        rate = None
        average_rate = getattr(self._stream, "average_rate", None)
        if average_rate:
            try:
                rate = float(average_rate)
            except (TypeError, ValueError):
                rate = None
        if not rate:
            # Handle the branch where rate is unavailable.
            base_rate = getattr(self._stream, "base_rate", None)
            if base_rate:
                try:
                    rate = float(base_rate)
                except (TypeError, ValueError):
                    rate = None
        if not rate:
            # Handle the branch where rate is unavailable.
            time_base = getattr(self._stream, "time_base", None)
            if time_base:
                try:
                    rate = 1.0 / float(time_base)
                except (TypeError, ValueError, ZeroDivisionError):
                    rate = None
        if not rate or rate <= 0:
            rate = 24.0
        delay = max(15, int(1000 / rate))
        return delay

    def _select_monitor(self) -> _MonitorBounds:
        """Select monitor."""
        monitors = _get_monitors()
        if not monitors:
            self._container.close()
            raise RuntimeError("No monitors available for second screen display.")
        target = monitors[1] if len(monitors) > 1 else monitors[0]
        x, y, w, h = target
        return _MonitorBounds(int(x), int(y), int(w), int(h))

    def _build_window(
        self,
        video_path: str,
        title: str | None,
        monitor: _MonitorBounds,
    ) -> ctk.CTkToplevel:
        """Build window."""
        win = ctk.CTkToplevel()
        win.title(title or os.path.basename(video_path))
        win.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
        win.configure(fg_color="black")
        win.update_idletasks()
        win.lift()
        try:
            win.attributes("-topmost", True)
            self._schedule(200, lambda: win.attributes("-topmost", False), window=win)
        except Exception:  # pragma: no cover - platform dependent
            pass
        return win

    def _render_next_frame(self) -> None:
        """Render next frame."""
        if self._stopped:
            return
        try:
            frame = next(self._frame_iterator)
        except StopIteration:
            if self._loop and self._restart_decoder():
                self._schedule(0, self._render_next_frame)
            else:
                self.close()
            return
        except Exception as exc:  # Tk callbacks must not propagate decoder errors
            self._show_playback_error(exc)
            self.close()
            return

        try:
            image = frame.to_image()
            self._display_image(image)
        except Exception as exc:
            self._show_playback_error(exc)
            self.close()
            return
        self._schedule(self._frame_delay, self._render_next_frame)

    def _schedule(self, delay: int, callback, *, window=None) -> str:
        """Schedule and track a callback so closing cancels all pending work."""
        target = window or self.window
        callback_id: str | None = None

        def run():
            if callback_id is not None:
                self._after_ids.discard(callback_id)
            if not self._stopped:
                callback()

        callback_id = target.after(delay, run)
        self._after_ids.add(callback_id)
        return callback_id

    def _restart_decoder(self) -> bool:
        """Rewind for the default muted, looping portrait reveal semantics."""
        try:
            self._container.seek(0, stream=self._stream, backward=True)
            self._frame_iterator = self._container.decode(self._stream)
            return True
        except Exception as exc:
            self._show_playback_error(exc)
            return False

    @staticmethod
    def _show_playback_error(exc) -> None:
        from tkinter import messagebox
        try:
            messagebox.showerror("Video Playback Error", f"Unable to continue video playback: {exc}")
        except Exception:
            pass

    def _display_image(self, image: Image.Image) -> None:
        """Internal helper for display image."""
        if not self.window.winfo_exists():
            return
        width = max(1, self.window.winfo_width())
        height = max(1, self.window.winfo_height())
        if width <= 1 or height <= 1:
            self._schedule(50, lambda img=image: self._display_image(img))
            return

        frame_ratio = image.width / image.height if image.height else 1.0
        window_ratio = width / height if height else frame_ratio

        if frame_ratio >= window_ratio:
            target_width = width
            target_height = int(width / frame_ratio)
        else:
            target_height = height
            target_width = int(height * frame_ratio)

        if target_width > 0 and target_height > 0:
            image = image.resize((target_width, target_height), _RESAMPLE_MODE)

        photo = ImageTk.PhotoImage(image)
        self._image_label.configure(image=photo)
        self._image_label.image = photo

    def close(self, event=None) -> None:  # noqa: D401 - Tkinter callback signature
        """Close the operation."""
        if self._stopped:
            return
        self._stopped = True
        for callback_id in tuple(self._after_ids):
            try:
                self.window.after_cancel(callback_id)
            except Exception:  # pragma: no cover - depends on event timing
                pass
        self._after_ids.clear()
        try:
            self._container.close()
        except Exception:  # pragma: no cover - cleanup best effort
            pass
        if self.window.winfo_exists():
            self.window.destroy()


def stop_active_video() -> None:
    """Stop and release the decoder for the current video reveal, if any."""
    global _active_player
    player, _active_player = _active_player, None
    if player is not None:
        player.close()


@log_function
def play_video_on_second_screen(
    video_path: str,
    title: str | None = None,
    *,
    loop: bool = True,
) -> ctk.CTkToplevel:
    """Play the provided video on the secondary monitor.

    Parameters
    ----------
    video_path:
        Absolute filesystem path to the video file to display.
    title:
        Optional window title to show while the video is playing.
    """

    if not video_path:
        raise ValueError("A video path must be provided.")
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)
    if av is None:
        raise RuntimeError("Video playback is unavailable because PyAV is not installed.")

    global _active_player
    stop_active_video()
    player = _SecondScreenVideoPlayer(video_path, title=title, loop=loop)
    _active_player = player
    # Keep a reference to prevent garbage collection from stopping playback.
    player.window._video_player_instance = player  # type: ignore[attr-defined]
    log_info(f"Playing video on second screen: {video_path}", func_name="play_video_on_second_screen")
    return player.window
