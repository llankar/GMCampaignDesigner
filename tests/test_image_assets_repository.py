"""Tests for image assets repository wrapper."""

from __future__ import annotations

from modules.image_assets.repository import ImageAssetsRepository


class _FakeWrapper:
    def __init__(self):
        self.items: list[dict] = []

    def load_items(self):
        return list(self.items)

    def save_item(self, item, *, key_field=None, original_key_value=None):
        key = item[key_field or "AssetId"]
        for index, existing in enumerate(self.items):
            if existing.get(key_field or "AssetId") == key:
                self.items[index] = dict(item)
                break
        else:
            self.items.append(dict(item))

    def save_items(self, items, *, replace=True):
        self.items = [dict(item) for item in items]


def test_upsert_by_hash_or_path_updates_existing_record():
    wrapper = _FakeWrapper()
    repository = ImageAssetsRepository(wrapper=wrapper)

    created = repository.upsert_by_hash_or_path(
        {
            "Name": "Map",
            "Path": "/tmp/map.png",
            "Hash": "abc",
            "Extension": ".png",
        }
    )
    updated = repository.upsert_by_hash_or_path(
        {
            "Name": "Map v2",
            "Path": "/tmp/map.png",
            "Hash": "abc",
            "Extension": ".png",
        }
    )

    assert len(wrapper.items) == 1
    assert updated["AssetId"] == created["AssetId"]
    assert wrapper.items[0]["Name"] == "Map v2"


def test_delete_stale_files_keeps_only_active_paths():
    wrapper = _FakeWrapper()
    wrapper.items = [
        {"AssetId": "1", "Path": "/a.png"},
        {"AssetId": "2", "Path": "/b.png"},
    ]
    repository = ImageAssetsRepository(wrapper=wrapper)

    removed = repository.delete_stale_files(["/a.png"])

    assert removed == 1
    assert [item["Path"] for item in wrapper.items] == ["/a.png"]


def test_list_paginated_supports_search_and_paging():
    wrapper = _FakeWrapper()
    wrapper.items = [
        {"AssetId": "1", "Name": "Forest", "Path": "/images/forest.png", "UpdatedAt": "2026-04-03T00:00:00+00:00"},
        {"AssetId": "2", "Name": "Castle", "Path": "/images/castle.png", "UpdatedAt": "2026-04-04T00:00:00+00:00"},
        {"AssetId": "3", "Name": "Dungeon", "Path": "/images/dungeon.jpg", "UpdatedAt": "2026-04-05T00:00:00+00:00"},
    ]
    repository = ImageAssetsRepository(wrapper=wrapper)

    page, total = repository.list_paginated(page=1, page_size=2, search=".png")

    assert total == 2
    assert [item["AssetId"] for item in page] == ["2", "1"]
