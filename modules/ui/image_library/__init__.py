"""Image library UI package."""

from __future__ import annotations

from typing import Any

__all__ = ["ImageBrowserPanel", "ImageResult", "ThumbnailCache", "ToolbarState"]


def __getattr__(name: str) -> Any:
    if name == "ImageBrowserPanel":
        from .browser_panel import ImageBrowserPanel

        return ImageBrowserPanel
    if name == "ImageResult":
        from .result_card import ImageResult

        return ImageResult
    if name == "ThumbnailCache":
        from .thumbnail_cache import ThumbnailCache

        return ThumbnailCache
    if name == "ToolbarState":
        from .toolbar import ToolbarState

        return ToolbarState
    raise AttributeError(name)
