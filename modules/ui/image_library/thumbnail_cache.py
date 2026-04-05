"""Thumbnail cache utilities for image browsing panels."""

from __future__ import annotations

import hashlib
import io
import os
from collections import OrderedDict
from pathlib import Path
from threading import RLock

from PIL import Image, ImageOps


class ThumbnailCache:
    """Hybrid thumbnail cache with in-memory LRU and optional disk backing."""

    def __init__(
        self,
        *,
        max_items: int = 512,
        disk_cache_dir: str | os.PathLike[str] | None = None,
        image_format: str = "PNG",
    ) -> None:
        self.max_items = max(1, int(max_items))
        self.image_format = image_format.upper()
        self._memory: OrderedDict[str, Image.Image] = OrderedDict()
        self._lock = RLock()
        self._disk_cache_dir = Path(disk_cache_dir).expanduser() if disk_cache_dir else None
        if self._disk_cache_dir:
            self._disk_cache_dir.mkdir(parents=True, exist_ok=True)

    def clear(self) -> None:
        """Clear in-memory cache only."""
        with self._lock:
            self._memory.clear()

    def get_thumbnail(self, source_path: str, size: tuple[int, int]) -> Image.Image:
        """Return a thumbnail image for the source path and requested size."""
        cache_key = self._make_cache_key(source_path=source_path, size=size)

        with self._lock:
            cached = self._memory.get(cache_key)
            if cached is not None:
                self._memory.move_to_end(cache_key)
                return cached.copy()

        if self._disk_cache_dir:
            disk_image = self._load_from_disk(cache_key)
            if disk_image is not None:
                self._remember(cache_key, disk_image)
                return disk_image.copy()

        image = self._build_thumbnail(source_path=source_path, size=size)
        self._remember(cache_key, image)
        if self._disk_cache_dir:
            self._store_to_disk(cache_key, image)
        return image.copy()

    def _remember(self, cache_key: str, image: Image.Image) -> None:
        """Store one entry in LRU memory cache."""
        with self._lock:
            self._memory[cache_key] = image.copy()
            self._memory.move_to_end(cache_key)
            while len(self._memory) > self.max_items:
                self._memory.popitem(last=False)

    def _load_from_disk(self, cache_key: str) -> Image.Image | None:
        """Load a thumbnail from disk cache if available."""
        path = self._disk_path(cache_key)
        if not path or not path.exists():
            return None
        try:
            with Image.open(path) as img:
                return img.copy()
        except Exception:
            return None

    def _store_to_disk(self, cache_key: str, image: Image.Image) -> None:
        """Write a thumbnail to disk cache."""
        path = self._disk_path(cache_key)
        if not path:
            return
        try:
            image.save(path, format=self.image_format)
        except Exception:
            return

    def _disk_path(self, cache_key: str) -> Path | None:
        """Return the disk path for a cache key."""
        if not self._disk_cache_dir:
            return None
        extension = self.image_format.lower()
        return self._disk_cache_dir / f"{cache_key}.{extension}"

    def _make_cache_key(self, *, source_path: str, size: tuple[int, int]) -> str:
        """Create deterministic cache key from path, mtime and size."""
        source = Path(source_path)
        try:
            stat = source.stat()
            marker = f"{source.resolve()}::{stat.st_mtime_ns}::{stat.st_size}::{size[0]}x{size[1]}"
        except OSError:
            marker = f"{source_path}::missing::{size[0]}x{size[1]}"
        return hashlib.sha256(marker.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_thumbnail(*, source_path: str, size: tuple[int, int]) -> Image.Image:
        """Generate thumbnail from source path."""
        with Image.open(source_path) as original:
            transformed = ImageOps.exif_transpose(original)
            rendered = transformed.convert("RGBA")
            rendered.thumbnail(size, Image.Resampling.LANCZOS)
            output = Image.new("RGBA", size, (32, 32, 32, 255))
            paste_x = (size[0] - rendered.width) // 2
            paste_y = (size[1] - rendered.height) // 2
            output.paste(rendered, (paste_x, paste_y), rendered)
            return output


class ThumbnailPlaceholderFactory:
    """Build reusable fallback images when a thumbnail cannot be loaded."""

    @staticmethod
    def build(size: tuple[int, int], text: str = "No Preview") -> Image.Image:
        """Build a plain fallback image.

        Text rendering is intentionally omitted to avoid adding a hard dependency on
        platform fonts in headless testing environments.
        """
        image = Image.new("RGBA", size, (48, 48, 48, 255))
        bio = io.BytesIO()
        image.save(bio, format="PNG")
        bio.seek(0)
        with Image.open(bio) as fallback:
            return fallback.copy()
