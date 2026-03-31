"""Storage helpers for campaign."""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_TEMPLATE_ENTITIES: tuple[str, ...] = (
    "pcs",
    "npcs",
    "scenarios",
    "factions",
    "bases",
    "places",
    "objects",
    "creatures",
    "informations",
    "clues",
    "maps",
    "books",
)


def normalize_campaign_db_path(db_path: str) -> str:
    """Normalize campaign DB path."""
    return os.path.abspath(os.path.normpath(db_path))


def ensure_campaign_directory(db_path: str) -> str:
    """Ensure campaign directory."""
    normalized_path = normalize_campaign_db_path(db_path)
    os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
    return normalized_path


def seed_default_templates(
    db_path: str,
    *,
    entities: Sequence[str] = DEFAULT_TEMPLATE_ENTITIES,
    project_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Copy missing campaign templates next to a newly created database."""

    normalized_path = normalize_campaign_db_path(db_path)
    campaign_dir = Path(normalized_path).parent
    template_dir = campaign_dir / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)

    project_root_path = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[3]
    for entity in entities:
        # Process each entity from entities.
        src = project_root_path / "modules" / entity / f"{entity}_template.json"
        dst = template_dir / f"{entity}_template.json"
        if dst.exists() or not src.exists():
            continue
        shutil.copyfile(src, dst)

    return template_dir


def ensure_campaign_support_tables(connection: sqlite3.Connection) -> None:
    """Ensure campaign support tables."""
    cursor = connection.cursor()
    for statement in _support_table_statements():
        cursor.execute(statement)
    connection.commit()


def _support_table_statements() -> Iterable[str]:
    """Internal helper for support table statements."""
    yield """
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_name TEXT,
            x INTEGER,
            y INTEGER,
            color TEXT
        )
    """
    yield """
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_name1 TEXT,
            npc_name2 TEXT,
            text TEXT,
            arrow_mode TEXT
        )
    """
    yield """
        CREATE TABLE IF NOT EXISTS shapes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            x INTEGER,
            y INTEGER,
            w INTEGER,
            h INTEGER,
            color TEXT,
            tag TEXT,
            z INTEGER
        )
    """
