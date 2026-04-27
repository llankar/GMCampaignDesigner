"""Thumbnail cache for GM Table ambiance media lists."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageOps

from modules.scenarios.gm_table.ambiance.repository import AmbianceMediaRecord

_THUMBNAIL_SIZE = (116, 66)


class ThumbnailCache:
    """Small in-memory LRU cache of CTk thumbnails."""

    def __init__(self, *, max_items: int = 220) -> None:
        self._max_items = max(40, int(max_items))
        self._cache: OrderedDict[str, tuple[float, ctk.CTkImage]] = OrderedDict()
        self._placeholder = self._build_placeholder()

    def get(self, record: AmbianceMediaRecord) -> ctk.CTkImage:
        """Return a thumbnail for a media record."""
        key = record.path
        cached = self._cache.get(key)
        if cached is not None and cached[0] == record.modified_at:
            self._cache.move_to_end(key)
            return cached[1]

        image = self._load(record)
        self._cache[key] = (record.modified_at, image)
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_items:
            self._cache.popitem(last=False)
        return image

    def clear(self) -> None:
        """Drop all cached thumbnails."""
        self._cache.clear()

    def _load(self, record: AmbianceMediaRecord) -> ctk.CTkImage:
        if record.media_type != "image":
            return self._placeholder

        path = Path(record.path)
        try:
            with Image.open(path) as source:
                render = source.convert("RGB")
                fitted = ImageOps.fit(render, _THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        except Exception:
            return self._placeholder
        return ctk.CTkImage(light_image=fitted, dark_image=fitted, size=_THUMBNAIL_SIZE)

    @staticmethod
    def _build_placeholder() -> ctk.CTkImage:
        image = Image.new("RGB", _THUMBNAIL_SIZE, color="#1F2937")
        return ctk.CTkImage(light_image=image, dark_image=image, size=_THUMBNAIL_SIZE)
