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
    SourceFolderName: str = ""
    Extension: str = ""
    Width: int | None = None
    Height: int | None = None
    FileSizeBytes: int | None = None
    Hash: str = ""
    NameNormalized: str = ""
    SearchTokens: list[str] = field(default_factory=list)
    Tags: list[str] = field(default_factory=list)
    SearchableBlob: str = ""
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
            "SourceFolderName": self.SourceFolderName,
            "Extension": self.Extension,
            "Width": self.Width,
            "Height": self.Height,
            "FileSizeBytes": self.FileSizeBytes,
            "Hash": self.Hash,
            "NameNormalized": self.NameNormalized,
            "SearchTokens": list(self.SearchTokens),
            "Tags": list(self.Tags),
            "SearchableBlob": self.SearchableBlob,
            "ImportedAt": self.ImportedAt,
            "UpdatedAt": self.UpdatedAt,
        }
