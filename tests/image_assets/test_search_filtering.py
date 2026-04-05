"""Regression tests for image search filtering behavior."""

from __future__ import annotations

from modules.image_assets.services.search_service import ImageAssetSearchService, ImageSearchFilters


class _FakeRepository:
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def list_all(self) -> list[dict]:
        return [dict(item) for item in self._items]


def test_search_images_applies_query_and_structured_filters() -> None:
    """Search service should combine full text query with width/tag/extension filters."""
    items = [
        {
            "AssetId": "1",
            "Name": "Forest Shrine",
            "Path": "/img/forest-shrine.png",
            "RelativePath": "forest-shrine.png",
            "SourceRoot": "/img",
            "Extension": "png",
            "Width": 1920,
            "Height": 1080,
            "Tags": ["forest", "shrine"],
            "NameNormalized": "forest shrine",
            "SearchableBlob": "forest shrine png",
            "UpdatedAt": "2026-04-05T10:00:00+00:00",
        },
        {
            "AssetId": "2",
            "Name": "Dungeon Map",
            "Path": "/img/dungeon-map.jpg",
            "RelativePath": "dungeon-map.jpg",
            "SourceRoot": "/img",
            "Extension": "jpg",
            "Width": 1024,
            "Height": 1024,
            "Tags": ["dungeon"],
            "NameNormalized": "dungeon map",
            "SearchableBlob": "dungeon map jpg",
            "UpdatedAt": "2026-04-05T11:00:00+00:00",
        },
    ]
    service = ImageAssetSearchService(repository=_FakeRepository(items))

    rows, total = service.search_images(
        query="forest",
        filters=ImageSearchFilters(extension="png", min_width=1200, tags=["forest"]),
        limit=20,
    )

    assert total == 1
    assert [row.asset_id for row in rows] == ["1"]
