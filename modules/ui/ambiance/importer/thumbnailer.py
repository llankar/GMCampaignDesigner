"""Thumbnail cache used by importer and campaign library list."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageOps

_DEFAULT_SIZE = (140, 84)


class WallpaperThumbnailer:
    """Generate and cache CTk thumbnails for local media files."""

    def __init__(self, *, size: tuple[int, int] = _DEFAULT_SIZE, max_items: int = 250) -> None:
        self._size = (max(32, int(size[0])), max(24, int(size[1])))
        self._max_items = max(40, int(max_items))
        self._cache: OrderedDict[str, tuple[float, ctk.CTkImage]] = OrderedDict()
        self._placeholder = self._build_placeholder()

    def get(self, path: str, *, media_type: str = "image") -> ctk.CTkImage:
        file_path = Path(path)
        if media_type != "image":
            return self._placeholder
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            return self._placeholder

        key = str(file_path.resolve())
        cached = self._cache.get(key)
        if cached is not None and cached[0] == mtime:
            self._cache.move_to_end(key)
            return cached[1]

        image = self._load_image(file_path)
        self._cache[key] = (mtime, image)
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_items:
            self._cache.popitem(last=False)
        return image

    def clear(self) -> None:
        self._cache.clear()

    def _load_image(self, path: Path) -> ctk.CTkImage:
        try:
            with Image.open(path) as source:
                render = source.convert("RGB")
                fitted = ImageOps.fit(render, self._size, Image.Resampling.LANCZOS)
        except Exception:
            return self._placeholder
        return ctk.CTkImage(light_image=fitted, dark_image=fitted, size=self._size)

    def _build_placeholder(self) -> ctk.CTkImage:
        image = Image.new("RGB", self._size, color="#1F2937")
        return ctk.CTkImage(light_image=image, dark_image=image, size=self._size)
