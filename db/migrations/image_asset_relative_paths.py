"""Idempotently migrate image_assets rows to campaign-relative references."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import shutil
import sqlite3
from pathlib import Path

from modules.image_assets.paths import (
    InvalidAssetReference,
    normalize_asset_reference,
    resolve_asset_reference,
)


@dataclass
class MigrationReport:
    updated: int = 0
    unchanged: int = 0
    issues: list[dict[str, str]] = field(default_factory=list)
    backup_path: str = ""


def migrate_image_asset_paths(database: str | Path, campaign_root: str | Path) -> MigrationReport:
    """Migrate one campaign DB, preserving unconvertible rows and reporting them."""
    db_path = Path(database).resolve()
    root = Path(campaign_root).resolve()
    report = MigrationReport()
    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(image_assets)")}
        if not columns:
            return report
        id_column = "AssetId" if "AssetId" in columns else "rowid"
        fields = [name for name in (id_column, "Path", "RelativePath", "SourceRoot") if name == "rowid" or name in columns]
        rows = connection.execute(f"SELECT {', '.join(fields)} FROM image_assets").fetchall()
        updates: list[tuple[str, str, str, object]] = []
        for row in rows:
            values = dict(zip(fields, row))
            identity = values[id_column]
            candidates = [values.get("RelativePath"), values.get("Path")]
            canonical = ""
            failures: list[str] = []
            for value in candidates:
                if not str(value or "").strip():
                    continue
                try:
                    canonical = normalize_asset_reference(str(value), root)
                    break
                except InvalidAssetReference as exc:
                    failures.append(str(exc))
            if not canonical:
                report.issues.append({"asset_id": str(identity), "path": str(values.get("Path") or ""), "reason": "; ".join(failures) or "missing reference"})
                continue
            resolved = resolve_asset_reference(canonical, root)
            if not resolved.is_file():
                report.issues.append({
                    "asset_id": str(identity),
                    "path": canonical,
                    "reason": "resolved file is missing",
                })
            desired = (canonical, canonical, "assets/image_library")
            current = (str(values.get("Path") or ""), str(values.get("RelativePath") or ""), str(values.get("SourceRoot") or ""))
            if current == desired:
                report.unchanged += 1
            else:
                updates.append((*desired, identity))
        if updates:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = db_path.with_suffix(db_path.suffix + f".pre-image-paths-{stamp}.bak")
            connection.commit()
            shutil.copy2(db_path, backup)
            report.backup_path = str(backup)
            connection.executemany(
                f"UPDATE image_assets SET Path=?, RelativePath=?, SourceRoot=? WHERE {id_column}=?",
                updates,
            )
            connection.commit()
            report.updated = len(updates)
    return report
