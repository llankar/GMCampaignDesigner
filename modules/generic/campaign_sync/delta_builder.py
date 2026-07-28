"""Inventory creation and compact delta bundle construction."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .change_detector import _content_files
from .delta_manifest import DeltaManifest, InventoryEntry
from .hashing import sha256_file


def build_inventory(root: Path, database_path: Path, *, database_snapshot_path: Path | None = None) -> tuple[InventoryEntry, ...]:
    root, database_path = Path(root).resolve(), Path(database_path).resolve()
    try:
        database_relative = database_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("campaign database must be inside the campaign root") from exc
    db_source = Path(database_snapshot_path) if database_snapshot_path else database_path
    entries = [InventoryEntry(database_relative, sha256_file(db_source), db_source.stat().st_size, "database")]
    for relative, path in _content_files(root):
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError(f"synchronized file escapes campaign root: {relative}") from exc
        kind = "asset" if relative.startswith(("assets/", "world_maps/")) else "extra_file"
        entries.append(InventoryEntry(relative, sha256_file(path), path.stat().st_size, kind))
    return tuple(sorted(entries, key=lambda item: item.path))


def compare_inventories(base: tuple[InventoryEntry, ...], current: tuple[InventoryEntry, ...]) -> tuple[tuple[InventoryEntry, ...], tuple[str, ...]]:
    old = {x.path: x for x in base}; new = {x.path: x for x in current}
    changed = tuple(x for path, x in sorted(new.items()) if x.file_type != "database" and old.get(path) != x)
    deleted = tuple(sorted(path for path in old.keys() - new.keys() if old[path].file_type != "database"))
    return changed, deleted


def write_delta_bundle(archive: Path, root: Path, database_snapshot: Path, database_relative: str,
                       sync: dict, base_revision: int, base_fingerprint: str,
                       base_inventory: tuple[InventoryEntry, ...], current_inventory: tuple[InventoryEntry, ...]) -> dict:
    changed, tombstones = compare_inventories(base_inventory, current_inventory)
    delta = DeltaManifest(base_revision, base_fingerprint, changed, tombstones, current_inventory)
    database_entry = next(x for x in current_inventory if x.file_type == "database")
    manifest = {"version": sync["bundle_version"], "bundle_mode": "campaign_delta", "sync": sync,
                "database": {"file_name": Path(database_relative).name, "relative_path": "database/campaign.db",
                             "sha256": database_entry.sha256, "size": database_entry.size},
                "delta": delta.to_dict(), "transfer_size": database_entry.size + sum(x.size for x in changed)}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(database_snapshot, "database/campaign.db")
        for entry in changed:
            source = (root / entry.path).resolve()
            try:
                source.relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError(f"delta payload escapes campaign root: {entry.path}") from exc
            bundle.write(source, f"payload/{entry.path}")
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
    return manifest
