"""Transparent VP8/VP9 WebM support."""

from __future__ import annotations

from collections import deque

from PIL import Image

from .errors import MediaDecodeError
from .pillow import decoded_frame_to_image, has_transparency

UNSUPPORTED_ALPHA_MESSAGE = (
    "Transparent WebM decoding is unsupported by the installed PyAV/FFmpeg "
    "backend (the VP8/VP9 auxiliary alpha stream is unavailable)."
)


def advertises_alpha(container: object, stream: object) -> bool:
    """Inspect Matroska and video-stream metadata for ``alpha_mode=1``."""
    format_name = str(getattr(getattr(container, "format", None), "name", "")).lower()
    if "webm" not in format_name and "matroska" not in format_name:
        return False
    metadata = {}
    metadata.update(getattr(container, "metadata", {}) or {})
    metadata.update(getattr(stream, "metadata", {}) or {})
    return any(
        str(key).lower().replace("-", "_") == "alpha_mode" and str(value).strip() not in {"", "0"}
        for key, value in metadata.items()
    )


class WebMAlphaDecoder:
    """Decode WebM through libvpx and expose its auxiliary alpha plane."""

    def __init__(self, av: object, path: str, codec_name: str):
        if codec_name not in {"vp8", "vp9"}:
            raise MediaDecodeError(UNSUPPORTED_ALPHA_MESSAGE)
        decoder = "libvpx-vp9" if codec_name == "vp9" else "libvpx"
        try:
            # FFmpeg's native VP8/VP9 decoders commonly discard Matroska
            # BlockAdditional alpha. Decode demuxed packets with an explicitly
            # selected libvpx context so this does not depend on av.open()
            # accepting ffmpeg-command-line-only ``-vcodec`` syntax.
            self._container = av.open(path)
            self._stream = self._container.streams.video[0]
            self._packets = self._container.demux(self._stream)
            self._codec = av.CodecContext.create(decoder, "r")
            source_context = self._stream.codec_context
            if source_context.extradata:
                self._codec.extradata = source_context.extradata
            self._decoded = deque()
        except Exception as exc:
            self.close()
            raise MediaDecodeError(UNSUPPORTED_ALPHA_MESSAGE) from exc

    def read_alpha(self) -> Image.Image:
        try:
            frame = self._next_frame()
            image = decoded_frame_to_image(frame)
            if not has_transparency(image):
                raise MediaDecodeError(UNSUPPORTED_ALPHA_MESSAGE)
            return image.getchannel("A")
        except Exception as exc:
            if isinstance(exc, MediaDecodeError):
                raise
            raise MediaDecodeError(UNSUPPORTED_ALPHA_MESSAGE) from exc

    def _next_frame(self):
        """Return one libvpx frame, looping while retaining packet side data."""
        while not self._decoded:
            try:
                packet = next(self._packets)
            except StopIteration:
                self._container.seek(0, stream=self._stream, backward=True)
                self._codec.flush_buffers()
                self._packets = self._container.demux(self._stream)
                try:
                    packet = next(self._packets)
                except StopIteration as exc:
                    raise MediaDecodeError(UNSUPPORTED_ALPHA_MESSAGE) from exc
            self._decoded.extend(self._codec.decode(packet))
        return self._decoded.popleft()

    def close(self) -> None:
        container = getattr(self, "_container", None)
        if container is not None:
            try:
                container.close()
            except Exception:
                pass


def combine_color_and_alpha(color: Image.Image, alpha: Image.Image) -> Image.Image:
    """Combine the ordinary decoded color with libvpx's auxiliary alpha."""
    result = color.convert("RGBA")
    if alpha.size != result.size:
        alpha = alpha.resize(result.size, Image.Resampling.BILINEAR)
    result.putalpha(alpha)
    return result
