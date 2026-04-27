"""Media loading helpers for ambiance playback."""

from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image

try:
    import av  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    av = None

from modules.ui.ambiance.models import AmbianceItem

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


@dataclass(slots=True)
class LoadedVideo:
    """Container for decoded-video resources."""

    container: object
    stream: object
    frame_iterator: object
    frame_delay_ms: int


def infer_media_type(path: str) -> str:
    """Infer media type from file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _IMAGE_EXTENSIONS:
        return "image"
    if ext in _VIDEO_EXTENSIONS:
        return "video"
    raise ValueError(f"Type de média non supporté: {path}")


def normalize_item(item: AmbianceItem, default_duration: float) -> AmbianceItem:
    """Return a normalized ambiance item with inferred media type and duration."""
    media_type = item.media_type or infer_media_type(item.path)
    duration = float(item.duration or default_duration)
    if duration <= 0:
        duration = float(default_duration)
    return AmbianceItem(
        path=item.path,
        media_type=media_type,  # type: ignore[arg-type]
        duration=duration,
        tags=tuple(item.tags or ()),
    )


def load_image(path: str) -> Image.Image:
    """Load an image from disk and return a detached copy."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with Image.open(path) as source:
        return source.copy().convert("RGBA")


def _calculate_frame_delay(stream) -> int:
    rate = None
    average_rate = getattr(stream, "average_rate", None)
    if average_rate:
        try:
            rate = float(average_rate)
        except (TypeError, ValueError):
            rate = None
    if not rate:
        base_rate = getattr(stream, "base_rate", None)
        if base_rate:
            try:
                rate = float(base_rate)
            except (TypeError, ValueError):
                rate = None
    if not rate:
        time_base = getattr(stream, "time_base", None)
        if time_base:
            try:
                rate = 1.0 / float(time_base)
            except (TypeError, ValueError, ZeroDivisionError):
                rate = None
    if not rate or rate <= 0:
        rate = 24.0
    return max(15, int(1000 / rate))


def load_video(path: str) -> LoadedVideo:
    """Open a video using PyAV and prepare a stream iterator."""
    if av is None:
        raise RuntimeError("PyAV est requis pour lire des vidéos d'ambiance.")
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    container = av.open(path)
    stream = next((s for s in container.streams if s.type == "video"), None)
    if stream is None:
        container.close()
        raise RuntimeError("Le fichier ne contient pas de flux vidéo.")
    stream.thread_type = "AUTO"
    iterator = container.decode(stream)
    return LoadedVideo(
        container=container,
        stream=stream,
        frame_iterator=iterator,
        frame_delay_ms=_calculate_frame_delay(stream),
    )
