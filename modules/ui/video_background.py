"""Video background rendering for map canvases.

Decodes video frames with PyAV and updates the map's base image layer on the
GM canvas, fullscreen canvas (if present), and exposes the latest frame for
web rendering.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:
    import av  # type: ignore
except Exception:  # pragma: no cover - handled at runtime
    av = None  # type: ignore

from PIL import Image, ImageTk


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".m4v"}


def is_video_path(path: str) -> bool:
    if not path:
        return False
    _, ext = os.path.splitext(str(path))
    return ext.lower() in VIDEO_EXTENSIONS


def _calc_frame_delay_ms(stream) -> int:
    """Return a sensible per-frame delay for the video stream.

    Prefer the container's reported average frame rate; fall back to other
    hints. Clamp to a practical range to avoid extremely slow playback from
    bad metadata.
    """
    candidates = []
    for attr in ("average_rate", "base_rate", "rate"):
        value = getattr(stream, attr, None)
        if value:
            try:
                fps = float(value)
                if fps and fps > 0:
                    candidates.append(fps)
            except (TypeError, ValueError):
                pass
    # time_base is seconds per tick; 1/time_base is ticks per second, not
    # strictly FPS, but in practice can be near it for some streams.
    if not candidates:
        time_base = getattr(stream, "time_base", None)
        if time_base:
            try:
                approx = float(1.0 / float(time_base))
                if approx and approx > 0:
                    candidates.append(approx)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    fps = None
    if candidates:
        # choose a reasonable candidate within [12, 60]
        fps = max(12.0, min(60.0, candidates[0]))
    if not fps:
        fps = 24.0
    # Convert to milliseconds
    delay_ms = int(1000.0 / fps)
    # lower bound to avoid timer storms
    return max(10, delay_ms)


@dataclass
class _StreamInfo:
    width: int
    height: int
    delay_ms: int


class CanvasVideoBackgroundPlayer:
    """Decode frames and paint them on the controller's canvases.

    Controller is expected to be an instance of DisplayMapController (or a
    compatible type) that has attributes: parent, canvas, base_id, base_tk,
    pan_x, pan_y, zoom, fs_canvas, fs_base_id, fs_base_tk, and a
    `_video_current_frame_pil` for web rendering.
    """

    def __init__(self, controller, path: str, *, loop: bool = True) -> None:
        if av is None:
            raise RuntimeError("PyAV is required for video backgrounds, but is not available.")
        if not path or not os.path.exists(path):
            raise FileNotFoundError(path)
        self._controller = controller
        self._path = path
        self._loop = loop
        self._container = None
        self._stream = None
        self._frame_iter = None
        self._after_id: Optional[str] = None
        self._stopped = False
        self._info: Optional[_StreamInfo] = None
        self._open_container()

    # Public API -----------------------------------------------------------
    @property
    def size(self) -> tuple[int, int]:
        if self._info is None:
            return (0, 0)
        return (self._info.width, self._info.height)

    def start(self) -> None:
        if self._stopped:
            return
        parent = getattr(self._controller, "parent", None)
        if parent is None:
            return
        try:
            parent.after(0, self._render_next)
        except Exception:
            pass

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        parent = getattr(self._controller, "parent", None)
        if parent and self._after_id:
            try:
                parent.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None
        try:
            if self._container is not None:
                self._container.close()
        except Exception:
            pass
        self._container = None
        self._stream = None
        self._frame_iter = None

    # Internals ------------------------------------------------------------
    def _open_container(self) -> None:
        if self._container is not None:
            try:
                self._container.close()
            except Exception:
                pass
        self._container = av.open(self._path)
        self._stream = next((s for s in self._container.streams if s.type == "video"), None)
        if self._stream is None:
            self._container.close()
            self._container = None
            raise RuntimeError("The selected file does not contain a video stream.")
        try:
            self._stream.thread_type = "AUTO"
        except Exception:
            pass
        delay_ms = _calc_frame_delay_ms(self._stream)
        width = int(getattr(self._stream, "width", 0) or 0)
        height = int(getattr(self._stream, "height", 0) or 0)
        if width <= 0 or height <= 0:
            # Fallback to first decoded frame to get size
            self._frame_iter = self._container.decode(self._stream)
            try:
                first = next(self._frame_iter)
            except StopIteration:
                raise RuntimeError("Unable to decode first frame from video.")
            image = first.to_image()
            width, height = image.width, image.height
            # also stash this as initial frame for consumers
            setattr(self._controller, "_video_current_frame_pil", image)
        self._info = _StreamInfo(width=width, height=height, delay_ms=delay_ms)
        # ensure we have a fresh iterator for normal decoding
        self._frame_iter = self._container.decode(self._stream)

    def _schedule(self) -> None:
        if self._stopped:
            return
        parent = getattr(self._controller, "parent", None)
        if parent is None or self._info is None:
            return
        try:
            self._after_id = parent.after(self._info.delay_ms, self._render_next)
        except Exception:
            self._after_id = None

    def _render_next(self) -> None:
        if self._stopped:
            return
        if self._frame_iter is None:
            self._open_container()
        frame = None
        try:
            frame = next(self._frame_iter)
        except StopIteration:
            if self._loop:
                try:
                    self._open_container()
                    frame = next(self._frame_iter)
                except Exception:
                    frame = None
            else:
                self.stop()
                return
        except Exception:
            # Best-effort recovery
            try:
                self._open_container()
                frame = next(self._frame_iter)
            except Exception:
                frame = None

        if frame is not None:
            image = frame.to_image()
            # Share the current frame for web rendering and size queries
            setattr(self._controller, "_video_current_frame_pil", image)
            # Optionally keep base_img dimensions in sync for code paths that
            # rely on size. Avoid excessive churn by only replacing when size matches.
            try:
                if getattr(self._controller, "base_img", None) is None:
                    self._controller.base_img = image
            except Exception:
                pass
            self._display_image(image)

        self._schedule()

    def _display_image(self, image: Image.Image) -> None:
        ctrl = self._controller
        canvas = getattr(ctrl, "canvas", None)
        if canvas is not None:
            try:
                if not canvas.winfo_exists():
                    canvas = None
            except Exception:
                canvas = None

        if canvas is not None:
            try:
                sw = max(1, int(image.width * float(getattr(ctrl, "zoom", 1.0) or 1.0)))
                sh = max(1, int(image.height * float(getattr(ctrl, "zoom", 1.0) or 1.0)))
            except Exception:
                sw, sh = image.width, image.height
            try:
                # Use a faster resample filter for continuous video updates
                fast_resample = getattr(ctrl, "_fast_resample", Image.BILINEAR)
                resized = image.resize((sw, sh), fast_resample)
            except Exception:
                resized = image
            tkimg = ImageTk.PhotoImage(resized)
            # keep a strong reference
            ctrl.base_tk = tkimg
            if getattr(ctrl, "base_id", None):
                try:
                    canvas.itemconfig(ctrl.base_id, image=tkimg)
                    canvas.coords(ctrl.base_id, getattr(ctrl, "pan_x", 0), getattr(ctrl, "pan_y", 0))
                except Exception:
                    pass
            else:
                try:
                    ctrl.base_id = canvas.create_image(getattr(ctrl, "pan_x", 0), getattr(ctrl, "pan_y", 0), image=tkimg, anchor="nw")
                except Exception:
                    pass

        # Fullscreen canvas update (if present)
        fs_canvas = getattr(ctrl, "fs_canvas", None)
        if fs_canvas is not None:
            try:
                if not fs_canvas.winfo_exists():
                    fs_canvas = None
            except Exception:
                fs_canvas = None
        if fs_canvas is not None:
            try:
                sw = max(1, int(image.width * float(getattr(ctrl, "zoom", 1.0) or 1.0)))
                sh = max(1, int(image.height * float(getattr(ctrl, "zoom", 1.0) or 1.0)))
            except Exception:
                sw, sh = image.width, image.height
            try:
                fast_resample = getattr(ctrl, "_fast_resample", Image.BILINEAR)
                resized = image.resize((sw, sh), fast_resample)
            except Exception:
                resized = image
            tkimg = ImageTk.PhotoImage(resized)
            ctrl.fs_base_tk = tkimg
            if getattr(ctrl, "fs_base_id", None):
                try:
                    fs_canvas.itemconfig(ctrl.fs_base_id, image=tkimg)
                    fs_canvas.coords(ctrl.fs_base_id, getattr(ctrl, "pan_x", 0), getattr(ctrl, "pan_y", 0))
                except Exception:
                    pass
            else:
                try:
                    ctrl.fs_base_id = fs_canvas.create_image(getattr(ctrl, "pan_x", 0), getattr(ctrl, "pan_y", 0), image=tkimg, anchor="nw")
                except Exception:
                    pass
