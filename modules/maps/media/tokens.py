"""Helpers that bridge persistent token dictionaries and runtime media state."""

from PIL import Image

from .decoder import MediaDecodeError, load_thumbnail
from .types import VIDEO, detect_media_type


def prepare_token_media(token: dict, resolved_path: str, size: int) -> bool:
    """Populate only in-memory PIL fields, returning whether media loaded."""
    media_type = detect_media_type(resolved_path, token.get("media_type"))
    token["media_type"] = media_type
    try:
        source = load_thumbnail(resolved_path, media_type)
    except MediaDecodeError:
        return False
    token["source_image"] = source
    token["pil_image"] = source.resize((int(size), int(size)), Image.Resampling.LANCZOS)
    return True


def register_token_animation(owner, token: dict, resolved_path: str) -> bool:
    """Register a video with an owner's animation manager when available."""
    if token.get("media_type") != VIDEO:
        return False
    manager = getattr(owner, "_token_animation_manager", None)
    if manager is None:
        ensure = getattr(owner, "_ensure_token_animation_manager", None)
        if callable(ensure):
            manager = ensure()
    return bool(manager and manager.register(token, resolved_path))
