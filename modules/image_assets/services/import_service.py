"""High-level filesystem import workflow for image assets."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable
import shutil

from PIL import Image, UnidentifiedImageError

from modules.image_assets.repository import ImageAssetsRepository
from modules.image_assets.paths import make_campaign_relative, normalize_asset_reference
from modules.helpers.config_helper import ConfigHelper
from modules.image_assets.services.import_options import ImageDirectoryImportOptions
from modules.image_assets.search.indexing import (
    build_search_tokens,
    build_searchable_blob,
    normalize_filename,
)

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_BATCH_SIZE = 1024 * 1024


@dataclass(slots=True)
class AssetImportError:
    """Error payload for one file that failed during import."""

    path: str
    reason: str


@dataclass(slots=True)
class ImageAssetsImportSummary:
    """Structured summary to feed user-facing dialogs."""

    roots_total: int
    roots_missing: list[str]
    scanned_files: int
    discovered_candidates: int
    imported_new: int
    updated: int
    skipped_unchanged: int
    skipped_duplicate: int
    skipped_existing: int
    errors: list[AssetImportError]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable mapping."""
        return {
            "roots_total": self.roots_total,
            "roots_missing": list(self.roots_missing),
            "scanned_files": self.scanned_files,
            "discovered_candidates": self.discovered_candidates,
            "imported_new": self.imported_new,
            "updated": self.updated,
            "skipped_unchanged": self.skipped_unchanged,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_existing": self.skipped_existing,
            "errors": [
                {"path": error.path, "reason": error.reason} for error in self.errors
            ],
        }


class ImageAssetImportService:
    """Filesystem importer that performs dedupe and metadata extraction."""

    def __init__(self, repository: ImageAssetsRepository | None = None) -> None:
        self.repository = repository or ImageAssetsRepository()

    def import_directories(
        self,
        paths: list[str],
        recursive: bool,
        reindex_changed_only: bool,
        update_existing_files: bool = True,
    ) -> ImageAssetsImportSummary:
        """Import image assets from one or more roots.

        Args:
            paths: Root directories selected by user.
            recursive: If True, walk subdirectories; otherwise scan direct children only.
            reindex_changed_only: If True, keep unchanged records as-is.
            update_existing_files: If True, replace matching existing rows with
                metadata read from the import directories.
        """
        options = ImageDirectoryImportOptions(
            recursive=recursive,
            reindex_changed_only=reindex_changed_only,
            update_existing_files=update_existing_files,
        )
        normalized_roots = self._normalize_roots(paths)
        campaign_root = Path(ConfigHelper.get_campaign_dir()).resolve()
        existing_items = self.repository.list_all()
        existing_by_path: dict[str, dict] = {}
        for item in existing_items:
            raw_path = str(item.get("Path") or "").strip()
            if not raw_path:
                continue
            try:
                existing_by_path[normalize_asset_reference(raw_path, campaign_root)] = item
            except ValueError:
                # Temporary lookup support for an old external absolute value;
                # the row is rewritten to the managed relative destination.
                existing_by_path[str(Path(raw_path).expanduser().resolve())] = item

        roots_missing: list[str] = []
        scanned_files = 0
        discovered_candidates = 0
        imported_new = 0
        updated = 0
        skipped_unchanged = 0
        skipped_duplicate = 0
        skipped_existing = 0
        errors: list[AssetImportError] = []

        seen_keys: set[str] = {
            self._compose_dedupe_key(item.get("Hash"), item.get("FileSizeBytes"))
            for item in existing_items
            if self._compose_dedupe_key(item.get("Hash"), item.get("FileSizeBytes"))
        }

        for root in normalized_roots:
            root_path = Path(root)
            if not root_path.exists() or not root_path.is_dir():
                roots_missing.append(str(root_path))
                continue

            for file_path in self._iter_image_files(
                root_path, recursive=options.recursive
            ):
                scanned_files += 1
                discovered_candidates += 1

                source_path = file_path.resolve()
                try:
                    stored_path = make_campaign_relative(source_path, campaign_root)
                    managed_path = source_path
                except ValueError:
                    managed_path = self._copy_external_asset(source_path, root_path, campaign_root)
                    stored_path = make_campaign_relative(managed_path, campaign_root)
                existing = existing_by_path.get(stored_path) or existing_by_path.get(str(source_path))

                try:
                    file_size = managed_path.stat().st_size
                    content_hash = self._compute_sha256(managed_path)
                except OSError as exc:
                    errors.append(
                        AssetImportError(
                            path=str(source_path), reason=f"stat/hash failed: {exc}"
                        )
                    )
                    continue

                dedupe_key = self._compose_dedupe_key(content_hash, file_size)
                if existing is None and dedupe_key in seen_keys:
                    skipped_duplicate += 1
                    continue

                if existing is not None and not options.update_existing_files:
                    skipped_existing += 1
                    continue

                unchanged = bool(
                    existing
                    and str(existing.get("Hash") or "") == content_hash
                    and int(existing.get("FileSizeBytes") or 0) == file_size
                )

                if unchanged and options.reindex_changed_only:
                    skipped_unchanged += 1
                    continue

                width: int | None = None
                height: int | None = None
                if not unchanged:
                    try:
                        width, height = self._read_dimensions(managed_path)
                    except (OSError, UnidentifiedImageError) as exc:
                        errors.append(
                            AssetImportError(
                                path=str(source_path), reason=f"metadata read failed: {exc}"
                            )
                        )
                        continue
                else:
                    width = self._as_optional_int(
                        existing.get("Width") if existing else None
                    )
                    height = self._as_optional_int(
                        existing.get("Height") if existing else None
                    )

                stem = file_path.stem
                tags: list[str] = []
                name_normalized = normalize_filename(stem)
                search_tokens = build_search_tokens(
                    name_normalized=name_normalized, tags=tags
                )
                searchable_blob = build_searchable_blob(
                    name=stem,
                    path=stored_path,
                    relative_path=stored_path,
                    source_root="assets/image_library",
                    extension=file_path.suffix.lower().lstrip("."),
                    tags=tags,
                    name_normalized=name_normalized,
                    search_tokens=search_tokens,
                    source_folder_name=file_path.parent.name,
                )

                payload = {
                    "Name": stem,
                    "Path": stored_path,
                    "RelativePath": stored_path,
                    "SourceRoot": "assets/image_library",
                    "SourceFolderName": file_path.parent.name,
                    "Extension": file_path.suffix.lower().lstrip("."),
                    "Width": width,
                    "Height": height,
                    "FileSizeBytes": file_size,
                    "Hash": content_hash,
                    "NameNormalized": name_normalized,
                    "SearchTokens": search_tokens,
                    "Tags": tags,
                    "SearchableBlob": searchable_blob,
                }

                saved = (
                    self.repository.replace_by_path(payload)
                    if existing
                    else self.repository.upsert_by_hash_or_path(payload)
                )
                existing_by_path[stored_path] = saved
                seen_keys.add(dedupe_key)

                if existing:
                    updated += 1
                else:
                    imported_new += 1

        return ImageAssetsImportSummary(
            roots_total=len(normalized_roots),
            roots_missing=roots_missing,
            scanned_files=scanned_files,
            discovered_candidates=discovered_candidates,
            imported_new=imported_new,
            updated=updated,
            skipped_unchanged=skipped_unchanged,
            skipped_duplicate=skipped_duplicate,
            skipped_existing=skipped_existing,
            errors=errors,
        )

    @staticmethod
    def _normalize_roots(paths: Iterable[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw in paths:
            candidate = str(raw or "").strip()
            if not candidate:
                continue
            normalized = str(Path(candidate).expanduser().resolve())
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    @staticmethod
    def _iter_image_files(root_path: Path, *, recursive: bool) -> Iterable[Path]:
        iterator = root_path.rglob("*") if recursive else root_path.glob("*")
        for path in iterator:
            if path.is_file() and path.suffix.lower() in _ALLOWED_EXTENSIONS:
                yield path

    @staticmethod
    def _compute_sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(_BATCH_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _read_dimensions(path: Path) -> tuple[int, int]:
        with Image.open(path) as img:
            return int(img.width), int(img.height)

    @staticmethod
    def _compose_dedupe_key(hash_value: object, file_size: object) -> str:
        digest = str(hash_value or "").strip()
        size = str(file_size or "").strip()
        if not digest or not size:
            return ""
        return f"{digest}:{size}"

    @staticmethod
    def _compute_relative(file_path: Path, root_path: Path) -> str:
        try:
            return str(file_path.resolve().relative_to(root_path.resolve()))
        except ValueError:
            return file_path.name

    @classmethod
    def _copy_external_asset(cls, source: Path, source_root: Path, campaign_root: Path) -> Path:
        """Copy an external file into the managed library without overwriting."""
        folder = cls._safe_component(source_root.name or "imported")
        try:
            tail = source.relative_to(source_root.resolve())
        except ValueError:
            tail = Path(source.name)
        destination = campaign_root / "assets" / "image_library" / folder / tail
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.stat().st_size == source.stat().st_size and cls._compute_sha256(destination) == cls._compute_sha256(source):
                return destination
            counter = 2
            while True:
                candidate = destination.with_name(f"{destination.stem}_{counter}{destination.suffix}")
                if candidate.exists() and candidate.stat().st_size == source.stat().st_size and cls._compute_sha256(candidate) == cls._compute_sha256(source):
                    return candidate
                if not candidate.exists():
                    destination = candidate
                    break
                counter += 1
        shutil.copy2(source, destination)
        return destination

    @staticmethod
    def _safe_component(value: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value).strip("_")
        return cleaned or "imported"

    @staticmethod
    def _as_optional_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
