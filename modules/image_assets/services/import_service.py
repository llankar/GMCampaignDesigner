"""High-level filesystem import workflow for image assets."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

from modules.image_assets.repository import ImageAssetsRepository

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
            "errors": [
                {"path": error.path, "reason": error.reason}
                for error in self.errors
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
    ) -> ImageAssetsImportSummary:
        """Import image assets from one or more roots.

        Args:
            paths: Root directories selected by user.
            recursive: If True, walk subdirectories; otherwise scan direct children only.
            reindex_changed_only: If True, keep unchanged records as-is.
        """
        normalized_roots = self._normalize_roots(paths)
        existing_items = self.repository.list_all()
        existing_by_path = {
            str(item.get("Path") or "").strip(): item
            for item in existing_items
            if str(item.get("Path") or "").strip()
        }

        roots_missing: list[str] = []
        scanned_files = 0
        discovered_candidates = 0
        imported_new = 0
        updated = 0
        skipped_unchanged = 0
        skipped_duplicate = 0
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

            for file_path in self._iter_image_files(root_path, recursive=recursive):
                scanned_files += 1
                discovered_candidates += 1

                abs_path = str(file_path.resolve())
                existing = existing_by_path.get(abs_path)

                try:
                    file_size = file_path.stat().st_size
                    content_hash = self._compute_sha256(file_path)
                except OSError as exc:
                    errors.append(AssetImportError(path=abs_path, reason=f"stat/hash failed: {exc}"))
                    continue

                dedupe_key = self._compose_dedupe_key(content_hash, file_size)
                if existing is None and dedupe_key in seen_keys:
                    skipped_duplicate += 1
                    continue

                unchanged = bool(
                    existing
                    and str(existing.get("Hash") or "") == content_hash
                    and int(existing.get("FileSizeBytes") or 0) == file_size
                )

                if unchanged and reindex_changed_only:
                    skipped_unchanged += 1
                    continue

                width: int | None = None
                height: int | None = None
                if not unchanged:
                    try:
                        width, height = self._read_dimensions(file_path)
                    except (OSError, UnidentifiedImageError) as exc:
                        errors.append(AssetImportError(path=abs_path, reason=f"metadata read failed: {exc}"))
                        continue
                else:
                    width = self._as_optional_int(existing.get("Width") if existing else None)
                    height = self._as_optional_int(existing.get("Height") if existing else None)

                stem = file_path.stem
                name_normalized = self._normalize_name(stem)
                search_tokens = self._build_search_tokens(name_normalized)

                payload = {
                    "Name": stem,
                    "Path": abs_path,
                    "RelativePath": self._compute_relative(file_path=file_path, root_path=root_path),
                    "SourceRoot": str(root_path.resolve()),
                    "Extension": file_path.suffix.lower().lstrip("."),
                    "Width": width,
                    "Height": height,
                    "FileSizeBytes": file_size,
                    "Hash": content_hash,
                    "NameNormalized": name_normalized,
                    "SearchTokens": search_tokens,
                }

                saved = self.repository.upsert_by_hash_or_path(payload)
                existing_by_path[abs_path] = saved
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
    def _normalize_name(name: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(name or ""))
        return " ".join(cleaned.split())

    @classmethod
    def _build_search_tokens(cls, normalized_name: str) -> list[str]:
        if not normalized_name:
            return []
        parts = normalized_name.split()
        compact = normalized_name.replace(" ", "")
        ordered: list[str] = []
        for token in [*parts, compact]:
            token = token.strip()
            if token and token not in ordered:
                ordered.append(token)
        return ordered

    @staticmethod
    def _compute_relative(file_path: Path, root_path: Path) -> str:
        try:
            return str(file_path.resolve().relative_to(root_path.resolve()))
        except ValueError:
            return file_path.name

    @staticmethod
    def _as_optional_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
