"""Search service for image assets with in-memory and optional SQLite-FTS paths."""

from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Any, Literal

from modules.image_assets.repository import ImageAssetsRepository
from modules.image_assets.search.dto import ImageAssetSearchResultDTO
from modules.image_assets.search.indexing import (
    build_searchable_blob,
    normalize_extension,
    normalize_query,
    normalize_tag,
    tokenize_query,
)

SortOption = Literal[
    "relevance",
    "name_asc",
    "name_desc",
    "updated_desc",
    "updated_asc",
    "size_desc",
    "size_asc",
]

_FTS_THRESHOLD = 750


@dataclass(slots=True)
class ImageSearchFilters:
    """Structured filters accepted by `search_images`."""

    filename: str | None = None
    tags: list[str] = field(default_factory=list)
    extension: str | None = None
    source_folder_names: list[str] = field(default_factory=list)
    min_width: int | None = None
    max_width: int | None = None
    min_height: int | None = None
    max_height: int | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "ImageSearchFilters":
        """Create filters from a plain mapping."""
        source = dict(value or {})

        def _list(key: str) -> list[str]:
            raw = source.get(key)
            if raw is None:
                return []
            if isinstance(raw, list):
                return [str(v) for v in raw if str(v).strip()]
            candidate = str(raw).strip()
            return [candidate] if candidate else []

        def _int_or_none(key: str) -> int | None:
            raw = source.get(key)
            if raw is None or raw == "":
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        return cls(
            filename=str(source.get("filename") or "").strip() or None,
            tags=_list("tags"),
            extension=str(source.get("extension") or "").strip() or None,
            source_folder_names=_list("source_folder_names") or _list("source_folders"),
            min_width=_int_or_none("min_width"),
            max_width=_int_or_none("max_width"),
            min_height=_int_or_none("min_height"),
            max_height=_int_or_none("max_height"),
        )


class ImageAssetSearchService:
    """Search image assets for UI consumers with optional FTS acceleration."""

    def __init__(self, repository: ImageAssetsRepository | None = None) -> None:
        self.repository = repository or ImageAssetsRepository()

    def search_images(
        self,
        query: str | None = None,
        filters: ImageSearchFilters | dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
        sort: SortOption = "relevance",
    ) -> tuple[list[ImageAssetSearchResultDTO], int]:
        """Search images for GM Screen and global image picker dialog."""
        limit = max(1, int(limit or 50))
        offset = max(0, int(offset or 0))
        normalized_query = normalize_query(query)
        parsed_filters = (
            filters
            if isinstance(filters, ImageSearchFilters)
            else ImageSearchFilters.from_mapping(filters if isinstance(filters, dict) else None)
        )

        items = self.repository.list_all()
        indexed = [self._build_indexed_row(item) for item in items]

        matched: list[dict[str, Any]]
        if normalized_query and len(indexed) >= _FTS_THRESHOLD:
            fts_match = self._search_with_fts(indexed, normalized_query)
            if fts_match is None:
                matched = self._search_in_memory(indexed, normalized_query)
            else:
                matched = fts_match
        else:
            matched = self._search_in_memory(indexed, normalized_query)

        filtered = [row for row in matched if self._matches_filters(row, parsed_filters)]
        ordered = self._sort_rows(filtered, sort=sort, query=normalized_query)

        total = len(ordered)
        paged = ordered[offset : offset + limit]
        return [self._to_dto(row) for row in paged], total

    def _search_in_memory(self, rows: list[dict[str, Any]], normalized_query: str) -> list[dict[str, Any]]:
        if not normalized_query:
            return list(rows)

        terms = tokenize_query(normalized_query)
        if not terms:
            return list(rows)

        matched: list[dict[str, Any]] = []
        for row in rows:
            blob = str(row.get("searchable_blob") or "")
            if all(term in blob for term in terms):
                matched.append(row)
        return matched

    def _search_with_fts(self, rows: list[dict[str, Any]], normalized_query: str) -> list[dict[str, Any]] | None:
        terms = tokenize_query(normalized_query)
        if not terms:
            return list(rows)

        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE VIRTUAL TABLE image_search USING fts5(asset_id, searchable_blob)")
            conn.executemany(
                "INSERT INTO image_search(asset_id, searchable_blob) VALUES (?, ?)",
                [(str(row.get("asset_id") or ""), str(row.get("searchable_blob") or "")) for row in rows],
            )
            statement = " ".join(f'{term}*' for term in terms)
            cur = conn.execute(
                "SELECT asset_id FROM image_search WHERE image_search MATCH ?",
                (statement,),
            )
            matched_ids = {str(record[0]) for record in cur.fetchall()}
        except sqlite3.Error:
            return None
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

        return [row for row in rows if str(row.get("asset_id") or "") in matched_ids]

    def _matches_filters(self, row: dict[str, Any], filters: ImageSearchFilters) -> bool:
        if filters.filename:
            filename_term = normalize_query(filters.filename)
            if filename_term and filename_term not in str(row.get("name_normalized") or ""):
                return False

        if filters.extension:
            expected_ext = normalize_extension(filters.extension)
            if expected_ext and normalize_extension(str(row.get("extension") or "")) != expected_ext:
                return False

        if filters.tags:
            row_tags = {normalize_tag(tag) for tag in row.get("tags") or [] if normalize_tag(tag)}
            for requested in filters.tags:
                normalized_requested = normalize_tag(requested)
                if normalized_requested and normalized_requested not in row_tags:
                    return False

        if filters.source_folder_names:
            source_folder_name = str(row.get("source_folder_name") or "").strip().lower()
            allowed_source_folders = {
                str(folder_name).strip().lower()
                for folder_name in filters.source_folder_names
                if str(folder_name).strip()
            }
            if allowed_source_folders and source_folder_name not in allowed_source_folders:
                return False

        width = self._as_optional_int(row.get("width"))
        height = self._as_optional_int(row.get("height"))
        if filters.min_width is not None and (width is None or width < filters.min_width):
            return False
        if filters.max_width is not None and (width is None or width > filters.max_width):
            return False
        if filters.min_height is not None and (height is None or height < filters.min_height):
            return False
        if filters.max_height is not None and (height is None or height > filters.max_height):
            return False

        return True

    def _sort_rows(self, rows: list[dict[str, Any]], *, sort: SortOption, query: str) -> list[dict[str, Any]]:
        sort = sort if sort in {
            "relevance",
            "name_asc",
            "name_desc",
            "updated_desc",
            "updated_asc",
            "size_desc",
            "size_asc",
        } else "relevance"

        if sort == "name_asc":
            return sorted(rows, key=lambda row: str(row.get("name") or "").lower())
        if sort == "name_desc":
            return sorted(rows, key=lambda row: str(row.get("name") or "").lower(), reverse=True)
        if sort == "updated_asc":
            return sorted(rows, key=lambda row: str(row.get("updated_at") or ""))
        if sort == "updated_desc":
            return sorted(rows, key=lambda row: str(row.get("updated_at") or ""), reverse=True)
        if sort == "size_asc":
            return sorted(rows, key=lambda row: int(row.get("file_size_bytes") or 0))
        if sort == "size_desc":
            return sorted(rows, key=lambda row: int(row.get("file_size_bytes") or 0), reverse=True)

        # relevance
        terms = tokenize_query(query)
        if not terms:
            return sorted(rows, key=lambda row: str(row.get("updated_at") or ""), reverse=True)

        def _score(row: dict[str, Any]) -> tuple[int, int, str]:
            blob = str(row.get("searchable_blob") or "")
            token_score = sum(1 for token in terms if token in blob)
            name_hit = int(all(token in str(row.get("name_normalized") or "") for token in terms))
            return (name_hit, token_score, str(row.get("updated_at") or ""))

        return sorted(rows, key=_score, reverse=True)

    def _build_indexed_row(self, item: dict[str, Any]) -> dict[str, Any]:
        tags = item.get("Tags") if isinstance(item.get("Tags"), list) else []
        search_tokens = item.get("SearchTokens") if isinstance(item.get("SearchTokens"), list) else []
        searchable_blob = str(item.get("SearchableBlob") or "")
        if not searchable_blob:
            searchable_blob = self._compose_searchable_blob(item, tags=tags, search_tokens=search_tokens)

        return {
            "asset_id": str(item.get("AssetId") or ""),
            "name": str(item.get("Name") or ""),
            "path": str(item.get("Path") or ""),
            "relative_path": str(item.get("RelativePath") or ""),
            "source_root": str(item.get("SourceRoot") or ""),
            "source_folder_name": str(item.get("SourceFolderName") or ""),
            "extension": str(item.get("Extension") or ""),
            "width": self._as_optional_int(item.get("Width")),
            "height": self._as_optional_int(item.get("Height")),
            "file_size_bytes": self._as_optional_int(item.get("FileSizeBytes")),
            "tags": [str(tag) for tag in tags],
            "name_normalized": str(item.get("NameNormalized") or ""),
            "searchable_blob": searchable_blob,
            "updated_at": str(item.get("UpdatedAt") or ""),
        }

    @staticmethod
    def _compose_searchable_blob(item: dict[str, Any], *, tags: list[str], search_tokens: list[str]) -> str:
        return build_searchable_blob(
            name=str(item.get("Name") or ""),
            path=str(item.get("Path") or ""),
            relative_path=str(item.get("RelativePath") or ""),
            source_root=str(item.get("SourceRoot") or ""),
            extension=str(item.get("Extension") or ""),
            tags=tags,
            name_normalized=str(item.get("NameNormalized") or ""),
            search_tokens=search_tokens,
            source_folder_name=str(item.get("SourceFolderName") or ""),
        )

    @staticmethod
    def _to_dto(row: dict[str, Any]) -> ImageAssetSearchResultDTO:
        preview_path = str(row.get("path") or "")
        return ImageAssetSearchResultDTO(
            asset_id=str(row.get("asset_id") or ""),
            name=str(row.get("name") or ""),
            preview_path=preview_path,
            path=preview_path,
            relative_path=str(row.get("relative_path") or ""),
            source_root=str(row.get("source_root") or ""),
            source_folder_name=str(row.get("source_folder_name") or ""),
            extension=str(row.get("extension") or ""),
            width=ImageAssetSearchService._as_optional_int(row.get("width")),
            height=ImageAssetSearchService._as_optional_int(row.get("height")),
            file_size_bytes=ImageAssetSearchService._as_optional_int(row.get("file_size_bytes")),
            tags=[str(tag) for tag in row.get("tags") or []],
        )

    @staticmethod
    def _as_optional_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
