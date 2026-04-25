"""Helpers for exporting/restoring non-entity campaign bundle files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


_RANDOM_TABLE_FILE = Path("static/data/random_tables.json")
_RANDOM_TABLE_DIR = Path("static/data/random_tables")


def collect_full_campaign_extra_files(campaign_root: Path) -> List[Tuple[Path, str]]:
    """Collect extra files that must travel with full-campaign bundles.

    Returns tuples of (absolute_path, relative_path_posix).
    """
    root = Path(campaign_root).resolve()
    collected: List[Tuple[Path, str]] = []

    random_tables_file = (root / _RANDOM_TABLE_FILE).resolve()
    if random_tables_file.exists() and random_tables_file.is_file():
        collected.append((random_tables_file, _RANDOM_TABLE_FILE.as_posix()))

    random_tables_dir = (root / _RANDOM_TABLE_DIR).resolve()
    if random_tables_dir.exists() and random_tables_dir.is_dir():
        for file_path in sorted(random_tables_dir.rglob("*.json")):
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(root).as_posix()
            collected.append((file_path.resolve(), relative_path))

    return collected
