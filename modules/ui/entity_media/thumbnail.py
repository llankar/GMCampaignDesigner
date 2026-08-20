"""Thumbnail decoding for entity images and videos."""

from pathlib import Path

from PIL import Image, ImageDraw

from .types import media_type


class MediaDecodeError(RuntimeError):
    """Raised when supported media cannot be decoded."""


def load_media_thumbnail(path: str | Path, size=(256, 256), *, video_indicator=True):
    """Decode an image or the first video frame and return a fitted PIL image.

    PyAV is imported lazily so image previews remain available without it.
    """
    kind = media_type(path)
    try:
        if kind == "image":
            with Image.open(path) as source:
                image = source.convert("RGBA")
        elif kind == "video":
            try:
                import av  # type: ignore
            except ImportError as exc:
                raise MediaDecodeError("Video preview unavailable (PyAV is not installed).") from exc
            with av.open(str(path)) as container:
                stream = next((item for item in container.streams if item.type == "video"), None)
                if stream is None:
                    raise MediaDecodeError("The media does not contain a video stream.")
                frame = next(container.decode(stream), None)
                if frame is None:
                    raise MediaDecodeError("The video contains no decodable frames.")
                image = frame.to_image().convert("RGBA")
        else:
            raise MediaDecodeError("Unsupported media type.")
    except MediaDecodeError:
        raise
    except Exception as exc:
        raise MediaDecodeError(f"Unable to decode media: {exc}") from exc

    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    if kind == "video" and video_indicator:
        draw = ImageDraw.Draw(canvas)
        cx, cy = size[0] - 28, size[1] - 28
        draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(0, 0, 0, 180))
        draw.polygon(((cx - 5, cy - 9), (cx - 5, cy + 9), (cx + 10, cy)), fill="white")
    return canvas
