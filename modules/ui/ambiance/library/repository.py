"""Read/query facade over the campaign wallpaper index."""

from __future__ import annotations

from modules.ui.ambiance.library.index_store import CampaignWallpaperIndexStore
from modules.ui.ambiance.library.models import WallpaperLibraryItem, WallpaperQuery


class CampaignWallpaperRepository:
    """Query helpers used by ambiance UI."""

    def __init__(self, index_store: CampaignWallpaperIndexStore | None = None) -> None:
        self._store = index_store or CampaignWallpaperIndexStore()

    @property
    def store(self) -> CampaignWallpaperIndexStore:
        return self._store

    def list_items(self, query: WallpaperQuery | None = None) -> list[WallpaperLibraryItem]:
        query = query or WallpaperQuery()
        rows = self._store.load()

        search = query.search.strip().lower()
        tag_filter = {tag.strip().lower() for tag in query.tags if tag.strip()}
        media_type = query.media_type.strip().lower()
        orientation = query.orientation.strip().lower()

        filtered: list[WallpaperLibraryItem] = []
        for item in rows:
            if search and search not in item.filename.lower() and all(search not in tag.lower() for tag in item.tags):
                continue
            if media_type in {"image", "video"} and item.media_type != media_type:
                continue
            if tag_filter and not tag_filter.intersection({tag.lower() for tag in item.tags}):
                continue
            if orientation in {"landscape", "portrait", "square"} and not _matches_orientation(item, orientation):
                continue
            filtered.append(item)

        return _sort_items(filtered, query.sort_key)

    def find_by_ids(self, item_ids: list[str] | tuple[str, ...]) -> list[WallpaperLibraryItem]:
        if not item_ids:
            return []
        by_id = {item.id: item for item in self._store.load()}
        result: list[WallpaperLibraryItem] = []
        for item_id in item_ids:
            item = by_id.get(str(item_id))
            if item is not None:
                result.append(item)
        return result

    def rebuild(self) -> list[WallpaperLibraryItem]:
        return self._store.rebuild()


def _matches_orientation(item: WallpaperLibraryItem, orientation: str) -> bool:
    if not item.width or not item.height:
        return False
    if orientation == "landscape":
        return item.width > item.height
    if orientation == "portrait":
        return item.height > item.width
    if orientation == "square":
        return item.width == item.height
    return True


def _sort_items(items: list[WallpaperLibraryItem], sort_key: str) -> list[WallpaperLibraryItem]:
    if sort_key == "created_desc":
        return sorted(items, key=lambda item: item.created_at, reverse=True)
    if sort_key == "created_asc":
        return sorted(items, key=lambda item: item.created_at)
    if sort_key == "size_desc":
        return sorted(items, key=lambda item: item.filesize, reverse=True)
    if sort_key == "size_asc":
        return sorted(items, key=lambda item: item.filesize)
    return sorted(items, key=lambda item: item.filename.casefold())
