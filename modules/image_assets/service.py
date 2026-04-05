"""Service facade for image assets."""

from __future__ import annotations

from typing import Any, Iterable

from modules.image_assets.repository import ImageAssetsRepository


class ImageAssetsService:
    """Business-facing API for image asset persistence and retrieval."""

    def __init__(self, repository: ImageAssetsRepository | None = None) -> None:
        """Initialize service."""
        self.repository = repository or ImageAssetsRepository()

    def upsert_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upsert one image asset by hash/path."""
        return self.repository.upsert_by_hash_or_path(payload)

    def delete_stale_files(self, active_paths: Iterable[str]) -> int:
        """Delete records that no longer exist in inventory."""
        return self.repository.delete_stale_files(active_paths)

    def list_assets(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List/search assets with pagination."""
        return self.repository.list_paginated(page=page, page_size=page_size, search=search)
