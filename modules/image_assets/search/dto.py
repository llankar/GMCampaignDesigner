"""DTOs used by image-asset search consumers (GM screen + global dialogs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ImageAssetSearchResultDTO:
    """UI-friendly projection for image-search result rows."""

    asset_id: str
    name: str
    preview_path: str
    path: str
    relative_path: str
    source_root: str
    extension: str
    width: int | None
    height: int | None
    file_size_bytes: int | None
    tags: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Serialize DTO for UI layers expecting dictionaries."""
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "preview_path": self.preview_path,
            "path": self.path,
            "relative_path": self.relative_path,
            "source_root": self.source_root,
            "extension": self.extension,
            "width": self.width,
            "height": self.height,
            "file_size_bytes": self.file_size_bytes,
            "tags": list(self.tags),
        }
