from modules.scenarios.gm_table.ambiance.playlist_controller import add_missing_items_to_playlist
from modules.ui.ambiance.library.models import WallpaperLibraryItem


def _item(item_id: str, path: str) -> WallpaperLibraryItem:
    return WallpaperLibraryItem(
        id=item_id,
        relative_path=path,
        filename=f"{item_id}.jpg",
        media_type="image",
        width=100,
        height=80,
        filesize=1024,
        created_at=1.0,
        tags=(),
    )


def test_add_missing_items_preserves_order_and_skips_duplicates() -> None:
    playlist = [{"id": "a", "path": "a.jpg", "duration": 8.0}]
    items = [_item("a", "a.jpg"), _item("b", "b.jpg"), _item("c", "c.jpg")]

    result = add_missing_items_to_playlist(
        playlist_entries=playlist,
        library_items=items,
        default_duration=10.0,
    )

    assert result.added_count == 2
    assert result.already_present_count == 1
    assert [entry["id"] for entry in playlist] == ["a", "b", "c"]
