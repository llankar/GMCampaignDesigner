"""Transactional replacement of the media displayed by one map token."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.helpers.config_helper import ConfigHelper

from .decoder import MediaDecodeError, load_thumbnail
from .tokens import prepare_token_media
from .types import IMAGE_EXTENSIONS, VIDEO, VIDEO_EXTENSIONS, detect_media_type


@dataclass(frozen=True)
class MediaReplacementResult:
    """Outcome returned to the UI without displaying UI from this service."""

    success: bool
    error: str = ""


def _campaign_relative_path(path: str) -> str:
    """Return a portable campaign-relative path when the asset is in campaign."""
    candidate = Path(path).resolve()
    try:
        return candidate.relative_to(Path(ConfigHelper.get_campaign_dir()).resolve()).as_posix()
    except ValueError:
        return str(candidate)


def replace_token_media(controller, token: dict, selected_path: str) -> MediaReplacementResult:
    """Validate then atomically replace a token's media and runtime animation.

    Decoding occurs against a temporary dictionary, so an invalid selection cannot
    alter either the token or its currently registered video decoder.
    """
    if not isinstance(token, dict) or token.get("type") != "token":
        return MediaReplacementResult(False, "The selected item is not a token.")

    resolved_path = str(Path(selected_path).expanduser().resolve())
    if Path(resolved_path).suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
        return MediaReplacementResult(False, "The selected file is not a supported image or video.")
    media_type = detect_media_type(resolved_path)
    candidate = {"media_type": media_type}
    def restore_original() -> None:
        """Restore media fields and playback after a failed commit."""
        if media_type == VIDEO and manager is not None:
            manager.unregister(token)
        for key, value in old_media.items():
            if value is missing:
                token.pop(key, None)
            else:
                token[key] = value
        if old_type == VIDEO and manager is not None:
            old_path = old_media.get("image_path")
            old_path = "" if old_path is missing else (old_path or "")
            if old_path and not Path(str(old_path)).is_absolute():
                old_path = str(Path(ConfigHelper.get_campaign_dir()) / str(old_path))
            if old_path:
                manager.register(token, str(old_path))

    try:
        thumbnail = load_thumbnail(resolved_path, media_type)
        if not prepare_token_media(
            candidate,
            resolved_path,
            max(1, int(token.get("size", getattr(controller, "token_size", 48)))),
            source_image=thumbnail,
        ):
            raise MediaDecodeError("The selected media could not be decoded.")
    except Exception as exc:
        return MediaReplacementResult(False, str(exc))

    missing = object()
    old_media = {
        key: token.get(key, missing)
        for key in ("image_path", "media_type", "source_image", "pil_image", "tk_image")
    }
    old_type = token.get("media_type")
    manager = getattr(controller, "_token_animation_manager", None)
    if old_type == VIDEO and manager is not None:
        manager.unregister(token)

    token.update(candidate)
    token["image_path"] = _campaign_relative_path(resolved_path)
    try:
        if media_type == VIDEO:
            ensure_manager = getattr(controller, "_ensure_token_animation_manager", None)
            manager = ensure_manager() if callable(ensure_manager) else manager
            if manager is None or not manager.register(token, resolved_path):
                raise MediaDecodeError("The selected video could not be registered for playback.")

        display_frame = getattr(controller, "_display_token_frame", None)
        if callable(display_frame):
            display_frame(token, candidate["source_image"])
        web_update = getattr(controller, "_update_web_display_map", None)
        if getattr(controller, "_web_server_thread", None) and callable(web_update):
            web_update()
        persist = getattr(controller, "_persist_tokens", None)
        if callable(persist):
            persist()
    except Exception as exc:
        restore_original()
        # A rendering or downstream refresh may fail after the canvas was
        # updated. Best-effort restoration keeps that item consistent too.
        old_source = old_media.get("source_image")
        display_frame = getattr(controller, "_display_token_frame", None)
        if old_source is not missing and callable(display_frame):
            try:
                display_frame(token, old_source)
            except Exception:
                pass
        return MediaReplacementResult(False, str(exc))

    return MediaReplacementResult(True)
