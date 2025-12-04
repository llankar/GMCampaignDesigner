from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


ALLOWED_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".webp"}
UPLOAD_DIR_NAME = "whiteboard_uploads"


@dataclass
class UploadedImage:
    asset_key: str
    path: str
    width: int
    height: int


def _uploads_root() -> Path:
    base = Path(ConfigHelper.get_campaign_dir())
    uploads = base / UPLOAD_DIR_NAME
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


def is_allowed_extension(filename: str | None) -> bool:
    if not filename:
        return False
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _normalize_size(value: Iterable[float] | None, default: int) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return max(1, int(value))
    except Exception:
        return default
    try:
        numeric = list(value)
        if numeric:
            return max(1, int(numeric[0]))
    except Exception:
        return default
    return default


def save_uploaded_image(file_storage) -> UploadedImage:
    """Persist an uploaded image to the campaign-local folder."""

    if file_storage is None or not getattr(file_storage, "filename", None):
        raise ValueError("No file provided")

    filename = file_storage.filename
    if not is_allowed_extension(filename):
        raise ValueError("Unsupported image format")

    try:
        file_storage.stream.seek(0)
    except Exception:
        pass

    try:
        with Image.open(file_storage.stream) as img:
            safe_image = img.convert("RGBA")
            width, height = safe_image.size
            asset_key = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
            destination = _uploads_root() / asset_key
            safe_image.save(destination)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unable to process image: {exc}") from exc

    return UploadedImage(asset_key=asset_key, path=str(destination), width=width, height=height)


def resolve_uploaded_asset(asset_key: str | None) -> str | None:
    if not asset_key:
        return None
    candidate = _uploads_root() / asset_key
    if candidate.exists() and candidate.is_file():
        return str(candidate)
    return None


@lru_cache(maxsize=64)
def load_scaled_upload(asset_key: str, width: int, height: int) -> Image.Image:
    path = resolve_uploaded_asset(asset_key)
    if not path:
        raise FileNotFoundError("Uploaded image not found")

    with Image.open(path) as img:
        safe_image = img.convert("RGBA")
        width_px = _normalize_size(width, default=safe_image.width)
        height_px = _normalize_size(height, default=safe_image.height)
        return safe_image.resize((width_px, height_px), Image.LANCZOS)


def clear_upload_cache() -> None:
    load_scaled_upload.cache_clear()
