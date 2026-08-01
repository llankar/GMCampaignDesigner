"""Regression tests for image import deduplication."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.image_assets.services.import_service import ImageAssetImportService
from modules.image_assets.paths import normalize_asset_reference


@pytest.fixture(autouse=True)
def _active_campaign(tmp_path: Path, monkeypatch):
    """Treat each test's temporary directory as the active campaign root."""
    monkeypatch.setattr(
        "modules.image_assets.services.import_service.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )


class _FakeRepository:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def list_all(self) -> list[dict]:
        return [dict(item) for item in self.items]

    def upsert_by_hash_or_path(self, payload: dict) -> dict:
        existing = None
        for row in self.items:
            try:
                paths_match = normalize_asset_reference(row.get("Path", "")) == payload.get("Path")
            except ValueError:
                paths_match = str(row.get("Path", "")).replace("\\", "/").endswith(
                    str(payload.get("Path", ""))
                )
            if paths_match:
                existing = row
                break
        if existing is None:
            record = dict(payload)
            self.items.append(record)
            return record
        existing.update(payload)
        return dict(existing)

    def replace_by_path(self, payload: dict) -> dict:
        return self.upsert_by_hash_or_path(payload)


def test_import_directories_skips_duplicate_content(
    tmp_path: Path, monkeypatch
) -> None:
    """Importer should dedupe by content hash+size across distinct paths."""
    root = tmp_path / "assets"
    root.mkdir()
    first = root / "castle.png"
    second = root / "castle_copy.png"
    payload = b"same-image-payload"
    first.write_bytes(payload)
    second.write_bytes(payload)

    service = ImageAssetImportService(repository=_FakeRepository())
    monkeypatch.setattr(service, "_read_dimensions", lambda _path: (128, 64))

    summary = service.import_directories(
        paths=[str(root)],
        recursive=False,
        reindex_changed_only=True,
    )

    assert summary.imported_new == 1
    assert summary.updated == 0
    assert summary.skipped_duplicate == 1
    assert summary.scanned_files == 2


def test_import_directories_stores_source_folder_name(
    tmp_path: Path, monkeypatch
) -> None:
    """Importer should capture the parent directory leaf as SourceFolderName."""
    root = tmp_path / "assets"
    nested = root / "portraits"
    nested.mkdir(parents=True)
    image = nested / "hero.png"
    image.write_bytes(b"img")

    repository = _FakeRepository()
    service = ImageAssetImportService(repository=repository)
    monkeypatch.setattr(service, "_read_dimensions", lambda _path: (256, 256))

    summary = service.import_directories(
        paths=[str(root)],
        recursive=True,
        reindex_changed_only=True,
    )

    assert summary.imported_new == 1
    assert repository.items[0]["SourceFolderName"] == "portraits"


def test_import_directories_updates_existing_path_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    """Importer should replace matching existing path records by default."""
    root = tmp_path / "assets"
    root.mkdir()
    image = root / "hero.png"
    image.write_bytes(b"new-image-payload")

    abs_path = str(image.resolve())
    repository = _FakeRepository()
    repository.items.append(
        {
            "Name": "Old Hero",
            "Path": abs_path,
            "Hash": "old-hash",
            "FileSizeBytes": 1,
            "Width": 32,
            "Height": 32,
            "Tags": ["custom"],
        }
    )
    service = ImageAssetImportService(repository=repository)
    monkeypatch.setattr(service, "_read_dimensions", lambda _path: (512, 256))

    summary = service.import_directories(
        paths=[str(root)],
        recursive=False,
        reindex_changed_only=True,
    )

    assert summary.imported_new == 0
    assert summary.updated == 1
    assert repository.items[0]["Name"] == "hero"
    assert repository.items[0]["Width"] == 512
    assert repository.items[0]["Height"] == 256
    assert repository.items[0]["Tags"] == []
    assert repository.items[0]["Hash"] != "old-hash"


def test_import_directories_can_leave_existing_paths_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    """Importer should preserve matching rows when existing updates are disabled."""
    root = tmp_path / "assets"
    root.mkdir()
    image = root / "hero.png"
    image.write_bytes(b"new-image-payload")

    abs_path = str(image.resolve())
    repository = _FakeRepository()
    repository.items.append(
        {
            "Name": "Old Hero",
            "Path": abs_path,
            "Hash": "old-hash",
            "FileSizeBytes": 1,
            "Width": 32,
            "Height": 32,
            "Tags": ["custom"],
        }
    )
    service = ImageAssetImportService(repository=repository)
    monkeypatch.setattr(
        service,
        "_read_dimensions",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("should skip metadata read")
        ),
    )

    summary = service.import_directories(
        paths=[str(root)],
        recursive=False,
        reindex_changed_only=True,
        update_existing_files=False,
    )

    assert summary.imported_new == 0
    assert summary.updated == 0
    assert summary.skipped_duplicate == 0
    assert summary.skipped_existing == 1
    assert repository.items[0]["Name"] == "Old Hero"
    assert repository.items[0]["Hash"] == "old-hash"
    assert repository.items[0]["Tags"] == ["custom"]


def test_external_import_is_copied_and_only_relative_paths_are_persisted(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    external = tmp_path / "external" / "ships"
    external.mkdir(parents=True)
    (external / "xwing.png").write_bytes(b"xwing")
    monkeypatch.setattr(
        "modules.image_assets.services.import_service.ConfigHelper.get_campaign_dir",
        lambda: str(campaign),
    )
    repository = _FakeRepository()
    service = ImageAssetImportService(repository=repository)
    monkeypatch.setattr(service, "_read_dimensions", lambda _path: (64, 64))

    summary = service.import_directories([str(tmp_path / "external")], recursive=True, reindex_changed_only=True)

    assert summary.imported_new == 1
    row = repository.items[0]
    assert row["Path"] == row["RelativePath"] == "assets/image_library/external/ships/xwing.png"
    assert row["SourceRoot"] == "assets/image_library"
    assert not Path(row["Path"]).is_absolute()
    assert (campaign / row["Path"]).read_bytes() == b"xwing"


def test_external_import_collision_does_not_overwrite_different_file(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    destination = campaign / "assets" / "image_library" / "external" / "ship.png"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old")
    external = tmp_path / "external"
    external.mkdir()
    (external / "ship.png").write_bytes(b"new")
    monkeypatch.setattr(
        "modules.image_assets.services.import_service.ConfigHelper.get_campaign_dir",
        lambda: str(campaign),
    )
    repository = _FakeRepository()
    service = ImageAssetImportService(repository=repository)
    monkeypatch.setattr(service, "_read_dimensions", lambda _path: (64, 64))

    service.import_directories([str(external)], recursive=False, reindex_changed_only=True)

    assert destination.read_bytes() == b"old"
    assert (destination.parent / "ship_2.png").read_bytes() == b"new"
    assert repository.items[0]["Path"] == "assets/image_library/external/ship_2.png"
