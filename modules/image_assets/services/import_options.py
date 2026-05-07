"""Options for image asset directory imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageDirectoryImportOptions:
    """User-selected options that control directory import behavior."""

    recursive: bool
    reindex_changed_only: bool
    update_existing_files: bool = True
