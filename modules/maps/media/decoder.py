"""Public media decoding API (codec implementations live in ``decoders``)."""

from __future__ import annotations

from pathlib import Path
from PIL import Image
from .decoders import MediaDecodeError, VideoDecoder
from .decoders.pillow import fit_frame


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
            return fit_frame(image, max_size)
    except Exception as exc:
        raise MediaDecodeError(f"Unable to open image {path!r}: {exc}") from exc
