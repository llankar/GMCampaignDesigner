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

    def __init__(self, video_path: str, title: str | None = None) -> None:
        if av is None:
            raise RuntimeError("PyAV is required to play video files.")

        self._container = self._open_container(video_path)
        self._stream = self._get_video_stream()
        self._frame_iterator = self._container.decode(self._stream)
        self._frame_delay = self._calculate_frame_delay()
        self._after_id: str | None = None
        self._stopped = False

        monitor = self._select_monitor()
        self.window = self._build_window(video_path, title, monitor)
        self._image_label = tk.Label(self.window, bg="black")
        self._image_label.pack(fill="both", expand=True)

        self.window.bind("<Escape>", self.close)
        self.window.bind("<Button-1>", self.close)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        # Kick off playback after the window has had a chance to layout.
        self.window.after(0, self._render_next_frame)

    def _open_container(self, path: str):
        try:
            return av.open(path)
        except av.AVError as exc:  # pragma: no cover - depends on runtime files
            raise RuntimeError(f"Unable to open video file: {exc}") from exc

    def _get_video_stream(self):
        stream = next((s for s in self._container.streams if s.type == "video"), None)
        if stream is None:
            self._container.close()
            raise RuntimeError("The selected file does not contain a video stream.")
        stream.thread_type = "AUTO"
        return stream

    def _calculate_frame_delay(self) -> int:
        rate = None
        average_rate = getattr(self._stream, "average_rate", None)
        if average_rate:
            try:
                rate = float(average_rate)
            except (TypeError, ValueError):
                rate = None
        if not rate:
            base_rate = getattr(self._stream, "base_rate", None)
            if base_rate:
                try:
                    rate = float(base_rate)
                except (TypeError, ValueError):
                    rate = None
        if not rate:
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
        win = ctk.CTkToplevel()
        win.title(title or os.path.basename(video_path))
        win.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
        win.configure(fg_color="black")
        win.update_idletasks()
        win.lift()
        try:
            win.attributes("-topmost", True)
            win.after(200, lambda: win.attributes("-topmost", False))
        except Exception:  # pragma: no cover - platform dependent
            pass
        return win

    def _render_next_frame(self) -> None:
        if self._stopped:
            return
        try:
            frame = next(self._frame_iterator)
        except StopIteration:
            self.close()
            return
        except av.AVError as exc:  # pragma: no cover - depends on runtime file
            self.close()
            raise RuntimeError(f"Video playback error: {exc}") from exc

        image = frame.to_image()
        self._display_image(image)
        self._after_id = self.window.after(self._frame_delay, self._render_next_frame)

    def _display_image(self, image: Image.Image) -> None:
        if not self.window.winfo_exists():
            return
        width = max(1, self.window.winfo_width())
        height = max(1, self.window.winfo_height())
        if width <= 1 or height <= 1:
            self.window.after(50, lambda img=image: self._display_image(img))
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
        if self._stopped:
            return
        self._stopped = True
        if self._after_id and self.window.winfo_exists():
            try:
                self.window.after_cancel(self._after_id)
            except Exception:  # pragma: no cover - depends on event timing
                pass
            self._after_id = None
        try:
            self._container.close()
        except Exception:  # pragma: no cover - cleanup best effort
            pass
        if self.window.winfo_exists():
            self.window.destroy()


@log_function
def play_video_on_second_screen(video_path: str, title: str | None = None) -> ctk.CTkToplevel:
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

    player = _SecondScreenVideoPlayer(video_path, title=title)
    # Keep a reference to prevent garbage collection from stopping playback.
    player.window._video_player_instance = player  # type: ignore[attr-defined]
    log_info(f"Playing video on second screen: {video_path}", func_name="play_video_on_second_screen")
    return player.window
