"""Media type detection independent from the UI and decoder backend."""

from pathlib import Path

IMAGE = "image"
VIDEO = "video"

VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"})


def detect_media_type(path: str, stored_type: str | None = None) -> str:
    """Return ``video`` or ``image`` without opening the media.

    A valid persisted value wins, allowing renamed media to remain stable.
    Unknown extensions intentionally fall back to images for compatibility.
    """
    normalized = str(stored_type or "").strip().lower()
    if normalized in {IMAGE, VIDEO}:
        return normalized
    return VIDEO if Path(str(path or "")).suffix.lower() in VIDEO_EXTENSIONS else IMAGE
