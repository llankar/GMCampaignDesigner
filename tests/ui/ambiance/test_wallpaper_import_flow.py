"""Tests for campaign-local ambiance wallpaper import and index."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from modules.ui.ambiance.importer.service import WallpaperImportService
from modules.ui.ambiance.library.index_store import CampaignWallpaperIndexStore
from modules.ui.ambiance.library.models import WallpaperQuery
from modules.ui.ambiance.library.repository import CampaignWallpaperRepository


def _write_image(path: Path, *, size: tuple[int, int] = (128, 72)) -> None:
    _ = size
    path.parent.mkdir(parents=True, exist_ok=True)
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7YH0oAAAAASUVORK5CYII="
    )
    path.write_bytes(tiny_png)


def test_import_copies_files_into_campaign_wallpaper_folder(tmp_path: Path) -> None:
    source_dir = tmp_path / "external"
    campaign_dir = tmp_path / "campaign"
    source = source_dir / "my.wallpaper.png"
    _write_image(source)

    store = CampaignWallpaperIndexStore(str(campaign_dir))
    service = WallpaperImportService(store)

    result = service.import_files([str(source)], strategy="skip")

    assert result.imported_count == 1
    saved = store.load()
    assert len(saved) == 1
    copied_path = store.wallpapers_dir / saved[0].relative_path
    assert copied_path.exists()
    assert copied_path.parent == store.wallpapers_dir


def test_import_duplicate_behaviors_skip_replace_keep_both(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    source_a = tmp_path / "a.png"
    source_b = tmp_path / "b.png"
    source_same_name = tmp_path / "folder" / "a.png"
    _write_image(source_a, size=(128, 72))
    _write_image(source_b, size=(192, 108))
    _write_image(source_same_name, size=(192, 108))

    store = CampaignWallpaperIndexStore(str(campaign_dir))
    service = WallpaperImportService(store)

    service.import_files([str(source_a)], strategy="skip")
    skip_result = service.import_files([str(source_a)], strategy="skip")
    assert skip_result.skipped_count == 1

    replace_result = service.import_files([str(source_same_name)], strategy="replace")
    assert replace_result.imported_count == 1

    keep_both_result = service.import_files([str(source_a)], strategy="keep_both")
    assert keep_both_result.imported_count == 1
    assert len(store.load()) == 2


def test_repository_filters_and_rebuild(tmp_path: Path, monkeypatch) -> None:
    campaign_dir = tmp_path / "campaign"
    store = CampaignWallpaperIndexStore(str(campaign_dir))
    wall_dir = store.wallpapers_dir
    _write_image(wall_dir / "landscape.png", size=(1920, 1080))
    _write_image(wall_dir / "portrait.png", size=(900, 1600))
    
    class _ImageStub:
        def __init__(self, size):
            self.size = size

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_open(path):
        filename = Path(path).name
        return _ImageStub((1920, 1080) if filename == "landscape.png" else (900, 1600))

    monkeypatch.setattr("modules.ui.ambiance.library.index_store.Image.open", _fake_open)

    rebuilt = store.rebuild()
    payload = json.loads(store.index_path.read_text(encoding="utf-8"))

    assert len(rebuilt) == 2
    assert payload["version"] == 1

    repository = CampaignWallpaperRepository(store)
    landscape = repository.list_items(WallpaperQuery(orientation="landscape"))
    portrait = repository.list_items(WallpaperQuery(orientation="portrait"))

    assert [item.filename for item in landscape] == ["landscape.png"]
    assert [item.filename for item in portrait] == ["portrait.png"]
