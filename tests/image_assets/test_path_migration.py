"""Tests for the idempotent image-assets path migration."""

import sqlite3
from pathlib import Path

from db.migrations.image_asset_relative_paths import migrate_image_asset_paths


def _database(path: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE image_assets (AssetId TEXT PRIMARY KEY, Path TEXT, RelativePath TEXT, SourceRoot TEXT)"
        )
        connection.executemany("INSERT INTO image_assets VALUES (?, ?, ?, ?)", rows)
    return path


def test_migration_handles_moved_windows_and_relative_rows_idempotently(tmp_path):
    campaign = tmp_path / "moved-campaign"
    campaign.mkdir()
    db = _database(tmp_path / "Velaris.db", [
        ("windows", r"D:\Velaris\assets\image_library\ships\xwing.png", "", r"D:\Velaris"),
        ("relative", "assets\\image_library\\maps\\world.png", "assets/image_library/maps/world.png", "old"),
    ])

    first = migrate_image_asset_paths(db, campaign)
    second = migrate_image_asset_paths(db, campaign)

    assert first.updated == 2
    assert Path(first.backup_path).is_file()
    assert second.updated == 0
    assert second.unchanged == 2
    with sqlite3.connect(db) as connection:
        rows = connection.execute(
            "SELECT Path, RelativePath, SourceRoot FROM image_assets ORDER BY AssetId"
        ).fetchall()
    assert rows == [
        ("assets/image_library/maps/world.png",) * 2 + ("assets/image_library",),
        ("assets/image_library/ships/xwing.png",) * 2 + ("assets/image_library",),
    ]


def test_migration_reports_and_preserves_external_or_missing_reference(tmp_path):
    db = _database(tmp_path / "Velaris.db", [
        ("external", "/outside/image.png", "", "/outside"),
        ("missing", "", "", ""),
    ])

    report = migrate_image_asset_paths(db, tmp_path / "campaign")

    assert report.updated == 0
    assert {issue["asset_id"] for issue in report.issues} == {"external", "missing"}
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT Path, RelativePath FROM image_assets ORDER BY AssetId").fetchall() == [
            ("/outside/image.png", ""), ("", "")
        ]
