from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from modules.campaigns.services.campaign_storage import (
    DEFAULT_TEMPLATE_ENTITIES,
    ensure_campaign_directory,
    ensure_campaign_support_tables,
    normalize_campaign_db_path,
    seed_default_templates,
)


def test_normalize_campaign_db_path_returns_absolute_path(tmp_path: Path) -> None:
    relative = tmp_path / "campaigns" / ".." / "campaigns" / "alpha.db"

    normalized = normalize_campaign_db_path(str(relative))

    assert Path(normalized).is_absolute()
    assert normalized.endswith("alpha.db")


def test_ensure_campaign_directory_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "campaign" / "state.db"

    normalized = ensure_campaign_directory(str(db_path))

    assert Path(normalized).parent.exists()
    assert Path(normalized).name == "state.db"


def test_seed_default_templates_copies_missing_templates(tmp_path: Path) -> None:
    db_path = tmp_path / "campaigns" / "lot3.db"
    project_root = tmp_path / "project"

    for entity in DEFAULT_TEMPLATE_ENTITIES[:2]:
        entity_dir = project_root / "modules" / entity
        entity_dir.mkdir(parents=True)
        (entity_dir / f"{entity}_template.json").write_text(f"{{\"entity\": \"{entity}\"}}", encoding="utf-8")

    template_dir = seed_default_templates(
        str(db_path),
        entities=DEFAULT_TEMPLATE_ENTITIES[:2],
        project_root=project_root,
    )

    assert template_dir == db_path.parent / "templates"
    assert (template_dir / "pcs_template.json").read_text(encoding="utf-8") == '{"entity": "pcs"}'
    assert (template_dir / "npcs_template.json").read_text(encoding="utf-8") == '{"entity": "npcs"}'


def test_seed_default_templates_preserves_existing_files(tmp_path: Path) -> None:
    db_path = tmp_path / "campaigns" / "lot3.db"
    project_root = tmp_path / "project"
    entity_dir = project_root / "modules" / "pcs"
    entity_dir.mkdir(parents=True)
    (entity_dir / "pcs_template.json").write_text('{"entity": "source"}', encoding="utf-8")

    existing_template = db_path.parent / "templates" / "pcs_template.json"
    existing_template.parent.mkdir(parents=True)
    existing_template.write_text('{"entity": "existing"}', encoding="utf-8")

    seed_default_templates(str(db_path), entities=("pcs",), project_root=project_root)

    assert existing_template.read_text(encoding="utf-8") == '{"entity": "existing"}'


def test_seed_default_templates_uses_service_relative_project_root_when_not_provided(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "campaigns" / "lot3.db"
    monkeypatch.chdir(tmp_path)

    template_dir = seed_default_templates(str(db_path), entities=("pcs",))

    assert (template_dir / "pcs_template.json").exists()


def test_ensure_campaign_support_tables_creates_expected_tables() -> None:
    conn = sqlite3.connect(":memory:")

    ensure_campaign_support_tables(conn)

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"nodes", "links", "shapes"}.issubset(tables)
