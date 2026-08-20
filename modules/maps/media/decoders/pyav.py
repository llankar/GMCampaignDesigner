"""Generic PyAV decoder with transparent-WebM specialization."""

from __future__ import annotations

import threading

from PIL import Image

from .errors import MediaDecodeError
from .pillow import decoded_frame_to_image, fit_frame, has_transparency
from .webm import WebMAlphaDecoder, advertises_alpha, combine_color_and_alpha


class VideoDecoder:
    """Own one PyAV container and provide RGBA frames, looping at EOF."""

    def __init__(self, path: str, *, max_size: int = 256):
        self.path = str(path)
        self.max_size = max(16, int(max_size))
        self._lock = threading.Lock()
        self._closed = False
        self._alpha_decoder = None
        try:
            import av

            self._av = av
            self._container = av.open(self.path)
            self._stream = self._container.streams.video[0]
            self._stream.thread_type = "AUTO"
            self._frames = self._container.decode(self._stream)
            self._advertises_alpha = advertises_alpha(self._container, self._stream)
            rate = float(self._stream.average_rate or 12)
            self.frame_rate = min(15.0, max(1.0, rate))
        except Exception as exc:
            self.close()
            raise MediaDecodeError(f"Unable to open video {self.path!r}: {exc}") from exc

    def _next_frame(self):
        try:
            return next(self._frames)
        except StopIteration:
            try:
                self._container.seek(0, stream=self._stream, backward=True)
                self._frames = self._container.decode(self._stream)
                return next(self._frames)
            except Exception as exc:
                raise MediaDecodeError(f"Unable to loop video: {exc}") from exc
        except Exception as exc:
            raise MediaDecodeError(f"Unable to decode video frame: {exc}") from exc

    def read_frame(self) -> Image.Image:
        with self._lock:
            if self._closed:
                raise MediaDecodeError("decoder is closed")
            frame = self._next_frame()
            try:
                image = decoded_frame_to_image(frame)
                if getattr(self, "_advertises_alpha", False) and not has_transparency(image):
                    if self._alpha_decoder is None:
                        codec_name = str(getattr(getattr(self._stream, "codec_context", None), "name", ""))
                        self._alpha_decoder = WebMAlphaDecoder(self._av, self.path, codec_name)
                    image = combine_color_and_alpha(image, self._alpha_decoder.read_alpha())
                return fit_frame(image, self.max_size)
            except MediaDecodeError:
                raise
            except Exception as exc:
                raise MediaDecodeError(f"Unable to convert video frame: {exc}") from exc

    def close(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            if getattr(self, "_closed", False):
                return
            self._closed = True
            alpha_decoder = getattr(self, "_alpha_decoder", None)
            if alpha_decoder is not None:
                alpha_decoder.close()
            container = getattr(self, "_container", None)
            if container is not None:
                try:
                    container.close()
                except Exception:
                    pass
