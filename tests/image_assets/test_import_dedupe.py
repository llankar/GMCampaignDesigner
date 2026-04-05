"""Regression tests for image import deduplication."""

from __future__ import annotations

from pathlib import Path

from modules.image_assets.services.import_service import ImageAssetImportService


class _FakeRepository:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def list_all(self) -> list[dict]:
        return [dict(item) for item in self.items]

    def upsert_by_hash_or_path(self, payload: dict) -> dict:
        existing = None
        for row in self.items:
            if row.get("Path") == payload.get("Path"):
                existing = row
                break
        if existing is None:
            record = dict(payload)
            self.items.append(record)
            return record
        existing.update(payload)
        return dict(existing)


def test_import_directories_skips_duplicate_content(tmp_path: Path, monkeypatch) -> None:
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
