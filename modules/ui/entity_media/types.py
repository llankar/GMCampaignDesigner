"""Canonical supported media types used by entity portrait UIs."""

from pathlib import Path

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"})
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def media_type(path: str | Path | None) -> str | None:
    """Return ``image``, ``video``, or ``None`` from a path's suffix."""
    suffix = Path(str(path or "")).suffix.casefold()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return None


def portrait_filetypes() -> list[tuple[str, str]]:
    """Return Tk file-dialog filters for all supported portrait media."""
    images = ";".join(f"*{ext}" for ext in sorted(IMAGE_EXTENSIONS))
    videos = ";".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
    return [
        ("Image and Video Files", f"{images};{videos}"),
        ("Image Files", images),
        ("Video Files", videos),
        ("All Files", "*.*"),
    ]
