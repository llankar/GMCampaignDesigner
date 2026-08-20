"""Defensive PyAV video decoding with a still-image fallback contract."""

from __future__ import annotations

import threading
from pathlib import Path
from PIL import Image


class MediaDecodeError(RuntimeError):
    """Raised when a media thumbnail or frame cannot be decoded."""


def _fit_frame(image: Image.Image, max_size: int) -> Image.Image:
    frame = image.convert("RGBA")
    if max(frame.size) > max_size:
        frame.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return frame


class VideoDecoder:
    """Own one PyAV container and provide frames, looping at end of stream."""

    def __init__(self, path: str, *, max_size: int = 256):
        self.path = str(path)
        self.max_size = max(16, int(max_size))
        self._lock = threading.Lock()
        self._closed = False
        try:
            import av
            self._av = av
            self._container = av.open(self.path)
            self._stream = self._container.streams.video[0]
            self._stream.thread_type = "AUTO"
            self._frames = self._container.decode(self._stream)
            rate = float(self._stream.average_rate or 12)
            self.frame_rate = min(15.0, max(1.0, rate))
        except Exception as exc:
            self.close()
            raise MediaDecodeError(f"Unable to open video {self.path!r}: {exc}") from exc

    def read_frame(self) -> Image.Image:
        with self._lock:
            if self._closed:
                raise MediaDecodeError("decoder is closed")
            try:
                frame = next(self._frames)
            except StopIteration:
                try:
                    self._container.seek(0, stream=self._stream, backward=True)
                    self._frames = self._container.decode(self._stream)
                    frame = next(self._frames)
                except Exception as exc:
                    raise MediaDecodeError(f"Unable to loop video: {exc}") from exc
            except Exception as exc:
                raise MediaDecodeError(f"Unable to decode video frame: {exc}") from exc
            return _fit_frame(frame.to_image(), self.max_size)

    def close(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            if getattr(self, "_closed", False):
                return
            self._closed = True
            container = getattr(self, "_container", None)
            if container is not None:
                try:
                    container.close()
                except Exception:
                    pass


def load_thumbnail(path: str, media_type: str, *, max_size: int = 256) -> Image.Image:
    """Load an image or the first video frame; never retain a video decoder."""
    if not path or not Path(path).is_file():
        raise MediaDecodeError(f"Media not found: {path}")
    if media_type == "video":
        decoder = VideoDecoder(path, max_size=max_size)
        try:
            return decoder.read_frame()
        finally:
            decoder.close()
    try:
        with Image.open(path) as image:
            return _fit_frame(image, max_size)
    except Exception as exc:
        raise MediaDecodeError(f"Unable to open image {path!r}: {exc}") from exc
