"""Repository wrapper around GenericModelWrapper for image assets."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Iterable

from modules.generic.generic_model_wrapper import GenericModelWrapper


class ImageAssetsRepository:
    """Persist and query image asset records."""

    def __init__(self, wrapper: GenericModelWrapper | None = None) -> None:
        """Initialize repository with optional wrapper override."""
        self.wrapper = wrapper or GenericModelWrapper("image_assets")

    def upsert_by_hash_or_path(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or update an asset using hash first, then path fallback."""
        existing = self._find_existing(
            hash_value=str(payload.get("Hash") or "").strip(),
            path=str(payload.get("Path") or "").strip(),
        )

        now = self._utc_now_iso()
        merged = dict(existing or {})
        merged.update(payload)

        if existing:
            merged["AssetId"] = existing.get("AssetId")
            merged["ImportedAt"] = existing.get("ImportedAt") or payload.get("ImportedAt") or now
        else:
            merged["AssetId"] = str(payload.get("AssetId") or uuid.uuid4())
            merged["ImportedAt"] = payload.get("ImportedAt") or now

        merged["UpdatedAt"] = payload.get("UpdatedAt") or now
        self.wrapper.save_item(merged, key_field="AssetId")
        return merged

    def delete_stale_files(self, active_paths: Iterable[str]) -> int:
        """Delete rows that no longer map to known file paths."""
        normalized = {str(path).strip() for path in active_paths if str(path).strip()}
        items = self.wrapper.load_items() or []
        kept: list[dict[str, Any]] = []
        stale_count = 0
        for item in items:
            row_path = str(item.get("Path") or "").strip()
            if row_path and row_path in normalized:
                kept.append(item)
            elif row_path:
                stale_count += 1
            else:
                kept.append(item)

        if stale_count:
            self.wrapper.save_items(kept, replace=True)
        return stale_count

    def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return page of records and total count with lightweight search."""
        page = max(1, int(page or 1))
        page_size = max(1, int(page_size or 50))

        items = self.wrapper.load_items() or []
        filtered = self._apply_search(items, search)
        filtered.sort(key=lambda row: str(row.get("UpdatedAt") or ""), reverse=True)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def _find_existing(self, *, hash_value: str, path: str) -> dict[str, Any] | None:
        """Find one row by exact hash or exact path."""
        items = self.wrapper.load_items() or []
        if hash_value:
            for item in items:
                if str(item.get("Hash") or "").strip() == hash_value:
                    return item
        if path:
            for item in items:
                if str(item.get("Path") or "").strip() == path:
                    return item
        return None

    @staticmethod
    def _apply_search(items: list[dict[str, Any]], search: str | None) -> list[dict[str, Any]]:
        """Filter items on common textual fields."""
        term = str(search or "").strip().lower()
        if not term:
            return list(items)

        def _matches(item: dict[str, Any]) -> bool:
            tags = item.get("Tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]
            haystack = [
                str(item.get("Name") or ""),
                str(item.get("Path") or ""),
                str(item.get("RelativePath") or ""),
                str(item.get("Extension") or ""),
                str(item.get("Hash") or ""),
                " ".join(str(tag) for tag in tags),
            ]
            return any(term in value.lower() for value in haystack)

        return [item for item in items if _matches(item)]

    @staticmethod
    def _utc_now_iso() -> str:
        """Return ISO UTC timestamp with seconds precision."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
