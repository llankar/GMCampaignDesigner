"""Ambiance player for fullscreen playback on a second monitor."""

from __future__ import annotations

import random
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from modules.helpers.logging_helper import log_info, log_warning
from modules.ui.ambiance.media_loader import load_image, load_video, normalize_item
from modules.ui.ambiance.models import AmbianceItem, AmbiancePlaylist, AmbianceState
from modules.ui.ambiance.monitor import MonitorSelectionError, select_target_monitor
from modules.ui.ambiance.monitor_selector import normalize_target_monitor

_RESAMPLING = getattr(Image, "Resampling", Image)
_RESAMPLE_MODE = getattr(_RESAMPLING, "LANCZOS", Image.LANCZOS)


class SecondScreenAmbiancePlayer:
    """Persistent fullscreen ambiance player living on a target monitor."""

    def __init__(
        self,
        *,
        root: tk.Misc,
        allow_single_screen_fallback: bool = True,
        fallback_topmost: bool = True,
    ) -> None:
        self._root = root
        self._allow_single_screen_fallback = allow_single_screen_fallback
        self._fallback_topmost = fallback_topmost

        self._window: ctk.CTkToplevel | None = None
        self._canvas: tk.Label | None = None
        self._playlist = AmbiancePlaylist()
        self._runtime_items: list[AmbianceItem] = []
        self._order: list[int] = []
        self._state = AmbianceState()
        self._target_monitor_index: int | None = 0
        self._last_monitor_warning: str | None = None
        self._photo_ref = None
        self._video = None

    def configure_single_screen_fallback(self, allow: bool) -> None:
        """Configure how the player behaves when only one screen is available."""
        self._allow_single_screen_fallback = bool(allow)

    def set_playlist(self, playlist: AmbiancePlaylist) -> None:
        """Set playlist without starting playback."""
        self._playlist = playlist
        self._runtime_items = [
            normalize_item(item, playlist.default_duration) for item in playlist.items
        ]
        self._build_order()
        if self._state.current_index >= len(self._order):
            self._state.current_index = -1

    def set_target_monitor_index(self, monitor_index: int | None) -> None:
        """Set preferred monitor index used on next window creation."""
        if monitor_index is None:
            self._target_monitor_index = None
            return
        try:
            self._target_monitor_index = max(0, int(monitor_index))
        except Exception:
            self._target_monitor_index = None

    def start(self, playlist: AmbiancePlaylist | None = None) -> None:
        """Start ambiance playback."""
        if playlist is not None:
            self.set_playlist(playlist)
        if not self._runtime_items:
            raise ValueError("Playlist ambiance vide.")

        self._ensure_window()
        self.stop(clear_playlist=False)
        self._state.is_running = True
        self._state.is_paused = False
        self._state.current_index = -1
        self.next()
        log_info("Ambiance player started", func_name="SecondScreenAmbiancePlayer.start")

    def pause(self) -> None:
        """Pause playback."""
        if not self._state.is_running or self._state.is_paused:
            return
        self._state.is_paused = True
        self._cancel_scheduled()

    def resume(self) -> None:
        """Resume playback."""
        if not self._state.is_running or not self._state.is_paused:
            return
        self._state.is_paused = False
        self._render_current()

    def stop(self, *, clear_playlist: bool = False, close_window: bool = False) -> None:
        """Stop playback and clear frame resources."""
        self._cancel_scheduled()
        self._close_video()
        self._state.is_running = False
        self._state.is_paused = False
        self._state.current_index = -1
        if close_window:
            self._destroy_window()
        elif self._canvas is not None:
            self._canvas.configure(image="", text="Ambiance stoppée", fg="white", bg="black")
        if clear_playlist:
            self._playlist = AmbiancePlaylist()
            self._runtime_items = []
            self._order = []

    def next(self) -> None:
        """Move to next media item."""
        if not self._runtime_items:
            return
        if not self._state.is_running:
            self._state.is_running = True

        next_index = self._state.current_index + 1
        if next_index >= len(self._order):
            if not self._playlist.loop:
                self.stop()
                return
            self._build_order()
            next_index = 0

        self._state.current_index = next_index
        self._state.is_paused = False
        self._render_current()

    def previous(self) -> None:
        """Move to previous media item."""
        if not self._runtime_items:
            return
        if self._state.current_index <= 0:
            self._state.current_index = 0
        else:
            self._state.current_index -= 1
        self._render_current()

    def _build_order(self) -> None:
        self._order = list(range(len(self._runtime_items)))
        if self._playlist.shuffle:
            random.shuffle(self._order)

    def _ensure_window(self) -> None:
        if self._window is not None and self._window.winfo_exists() and self._canvas is not None:
            return

        from modules.ui.image_viewer import _get_monitors

        requested_index = self._target_monitor_index if self._target_monitor_index is not None else 0
        monitor_count = len(_get_monitors())
        target_index, warning_message = normalize_target_monitor(requested_index, monitor_count)
        self._last_monitor_warning = warning_message

        monitor = select_target_monitor(
            allow_single_screen_fallback=self._allow_single_screen_fallback,
            preferred_index=target_index,
        )

        self._window = ctk.CTkToplevel(self._root)
        self._window.title("Ambiance")
        self._window.geometry(
            f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}"
        )
        self._window.configure(fg_color="black")
        self._window.overrideredirect(True)

        if monitor.is_secondary:
            self._window.attributes("-topmost", True)
            self._window.after(250, lambda: self._window and self._window.attributes("-topmost", False))
        elif self._fallback_topmost:
            self._window.attributes("-topmost", True)
            log_warning(
                "Ambiance fallback on single monitor (topmost window).",
                func_name="SecondScreenAmbiancePlayer._ensure_window",
            )

        self._canvas = tk.Label(self._window, bg="black", bd=0, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        self._window.bind("<Escape>", lambda _event: self.stop(close_window=True))
        self._window.protocol("WM_DELETE_WINDOW", lambda: self.stop(close_window=True))

    def _destroy_window(self) -> None:
        """Close the ambiance render window and release widget references."""
        window = self._window
        self._window = None
        self._canvas = None
        self._photo_ref = None
        if window is not None and window.winfo_exists():
            window.destroy()


    def consume_last_monitor_warning(self) -> str | None:
        """Return and clear the latest monitor fallback warning."""
        warning = self._last_monitor_warning
        self._last_monitor_warning = None
        return warning

    def _render_current(self) -> None:
        if self._state.is_paused or not self._state.is_running:
            return
        self._cancel_scheduled()
        self._close_video()
        item = self._current_item()
        if item is None:
            self.stop()
            return

        try:
            if item.media_type == "video":
                self._start_video(item)
            else:
                self._show_image(item)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            log_warning(str(exc), func_name="SecondScreenAmbiancePlayer._render_current")
            self.next()

    def _current_item(self) -> AmbianceItem | None:
        if self._state.current_index < 0 or self._state.current_index >= len(self._order):
            return None
        return self._runtime_items[self._order[self._state.current_index]]

    def _fit_image(self, image: Image.Image) -> Image.Image:
        if self._window is None:
            return image
        width = max(1, self._window.winfo_width())
        height = max(1, self._window.winfo_height())
        if width <= 1 or height <= 1:
            self._window.update_idletasks()
            width = max(1, self._window.winfo_width())
            height = max(1, self._window.winfo_height())
        src_w, src_h = image.size
        scale = min(width / src_w, height / src_h, 1.0)
        new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
        return image.resize(new_size, _RESAMPLE_MODE)

    def _show_image(self, item: AmbianceItem) -> None:
        if self._canvas is None or self._window is None:
            return
        image = self._fit_image(load_image(item.path))

        previous_photo = self._photo_ref
        if previous_photo is not None:
            try:
                previous_image = ImageTk.getimage(previous_photo).convert("RGBA")
            except Exception:
                previous_image = None
        else:
            previous_image = None

        if previous_image is not None and previous_image.size == image.size:
            self._cross_dissolve(previous_image, image)
        else:
            photo = ImageTk.PhotoImage(image)
            self._canvas.configure(image=photo, text="")
            self._photo_ref = photo

        self._state.slide_started_at = time.monotonic()
        delay = max(250, int(item.duration * 1000))
        self._state.after_id = self._root.after(delay, self.next)

    def _cross_dissolve(self, start: Image.Image, end: Image.Image) -> None:
        if self._canvas is None:
            return
        steps = max(4, min(14, int(self._playlist.transition_ms / 45)))
        step_delay = max(20, int(self._playlist.transition_ms / steps))

        frames = [ImageTk.PhotoImage(Image.blend(start, end, idx / steps)) for idx in range(1, steps + 1)]

        def _advance(frame_idx: int) -> None:
            if self._canvas is None or frame_idx >= len(frames):
                return
            frame = frames[frame_idx]
            self._canvas.configure(image=frame, text="")
            self._photo_ref = frame
            if frame_idx + 1 < len(frames):
                self._state.after_id = self._root.after(step_delay, lambda: _advance(frame_idx + 1))

        _advance(0)

    def _start_video(self, item: AmbianceItem) -> None:
        if self._canvas is None:
            return
        self._video = load_video(item.path)
        self._render_video_frame()

    def _render_video_frame(self) -> None:
        if self._state.is_paused or not self._state.is_running or self._video is None:
            return
        if self._canvas is None:
            return
        try:
            frame = next(self._video.frame_iterator)
        except StopIteration:
            self._close_video()
            self.next()
            return

        image = self._fit_image(frame.to_image().convert("RGBA"))
        photo = ImageTk.PhotoImage(image)
        self._canvas.configure(image=photo, text="")
        self._photo_ref = photo
        self._state.video_after_id = self._root.after(
            self._video.frame_delay_ms,
            self._render_video_frame,
        )

    def _cancel_scheduled(self) -> None:
        if self._state.after_id:
            try:
                self._root.after_cancel(self._state.after_id)
            except Exception:
                pass
            self._state.after_id = None
        if self._state.video_after_id:
            try:
                self._root.after_cancel(self._state.video_after_id)
            except Exception:
                pass
            self._state.video_after_id = None

    def _close_video(self) -> None:
        if self._video is None:
            return
        try:
            self._video.container.close()
        except Exception:
            pass
        self._video = None


def show_single_screen_rejection(message: str) -> None:
    """Display explicit rejection message when no fallback is allowed."""
    messagebox.showinfo("Ambiance", message)
