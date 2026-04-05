"""Data models for image assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ImageAssetRecord:
    """Canonical payload for image asset catalog rows."""

    AssetId: str
    Name: str
    Path: str
    RelativePath: str = ""
    SourceRoot: str = ""
    Extension: str = ""
    Width: int | None = None
    Height: int | None = None
    FileSizeBytes: int | None = None
    Hash: str = ""
    Tags: list[str] = field(default_factory=list)
    ImportedAt: str = ""
    UpdatedAt: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping for persistence."""
        return {
            "AssetId": self.AssetId,
            "Name": self.Name,
            "Path": self.Path,
            "RelativePath": self.RelativePath,
            "SourceRoot": self.SourceRoot,
            "Extension": self.Extension,
            "Width": self.Width,
            "Height": self.Height,
            "FileSizeBytes": self.FileSizeBytes,
            "Hash": self.Hash,
            "Tags": list(self.Tags),
            "ImportedAt": self.ImportedAt,
            "UpdatedAt": self.UpdatedAt,
        }
