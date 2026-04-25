"""Regression tests for cross campaign asset service."""

import sys
import types
import sqlite3

import pytest

if "winsound" not in sys.modules:
    winsound_stub = types.ModuleType("winsound")
    winsound_stub.SND_FILENAME = 0
    winsound_stub.SND_ASYNC = 0
    winsound_stub.SND_PURGE = 0

    def _noop(*_args, **_kwargs):
        """Internal helper for noop."""
        return None

    winsound_stub.PlaySound = _noop
    sys.modules["winsound"] = winsound_stub

from modules.generic.cross_campaign_asset_service import (
    CampaignDatabase,
    _rewrite_record_paths,
    collect_assets,
    export_bundle,
    install_full_campaign_bundle,
    analyze_bundle,
    apply_import,
)


def test_export_bundle_raises_when_database_missing(tmp_path):
    """Verify that export bundle raises when database missing."""
    destination = tmp_path / "export.zip"
    source_campaign = CampaignDatabase(
        name="MissingDB",
        root=tmp_path,
        db_path=tmp_path / "does_not_exist.db",
    )

    with pytest.raises(FileNotFoundError):
        export_bundle(
            destination=destination,
            source_campaign=source_campaign,
            selected_records={},
            include_database=True,
        )

    assert not destination.exists()


def test_collect_assets_includes_image_library_files(tmp_path):
    """Image library entries should include file references for bundle export."""
    campaign_root = tmp_path / "campaign"
    image_file = campaign_root / "imported" / "tiles" / "forest.png"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    image_file.write_bytes(b"image-bytes")

    record = {
        "Name": "Forest Tile",
        "Path": str(image_file.resolve()),
        "RelativePath": "imported/tiles/forest.png",
    }

    assets = collect_assets("image_assets", [record], campaign_root)

    assert len(assets) == 1
    assert assets[0].asset_type == "image_library"
    assert assets[0].original_path == "imported/tiles/forest.png"
    assert assets[0].absolute_path == image_file.resolve()


def test_rewrite_record_paths_updates_image_library_fields(tmp_path):
    """Image library rows should update Path + RelativePath after import."""
    target_campaign_root = (tmp_path / "target").resolve()
    replacement = "assets/image_library/imported/tiles/forest.png"
    record = {
        "Name": "Forest Tile",
        "Path": "/old/source/forest.png",
        "RelativePath": "imported/tiles/forest.png",
        "SourceRoot": "/old/source",
    }

    updated = _rewrite_record_paths(
        "image_assets",
        record,
        {"imported/tiles/forest.png": replacement},
        target_campaign_root=target_campaign_root,
    )

    assert updated["RelativePath"] == replacement
    assert updated["Path"] == str((target_campaign_root / replacement).resolve())
    assert updated["SourceRoot"] == str(target_campaign_root)


def test_export_bundle_full_campaign_includes_image_assets_even_without_selection(tmp_path, monkeypatch):
    """Full campaign exports should still include image library records/assets."""
    campaign_root = tmp_path / "source_campaign"
    campaign_root.mkdir(parents=True, exist_ok=True)
    db_path = campaign_root / "campaign.db"
    sqlite3.connect(db_path).close()
    image_file = campaign_root / "assets" / "image_library" / "tiles" / "forest.png"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    image_file.write_bytes(b"forest-bytes")

    source_campaign = CampaignDatabase(name="Source", root=campaign_root, db_path=db_path)
    destination = tmp_path / "bundle.zip"

    def fake_load_entities(entity_type, _db_path):
        if entity_type == "image_assets":
            return [{"Name": "Forest Tile", "RelativePath": "assets/image_library/tiles/forest.png"}]
        return []

    monkeypatch.setattr("modules.generic.cross_campaign_asset_service.load_entities", fake_load_entities)

    manifest = export_bundle(destination, source_campaign, selected_records={}, include_database=True)

    assert manifest["entities"]["image_assets"]["count"] == 1
    assert any(asset.get("asset_type") == "image_library" for asset in manifest["assets"])


def test_install_full_campaign_bundle_restores_random_tables_files(tmp_path):
    """Installing a full campaign bundle should restore random table JSON files."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()
    random_tables_file = source_root / "static" / "data" / "random_tables" / "encounters.json"
    random_tables_file.parent.mkdir(parents=True, exist_ok=True)
    random_tables_file.write_text('{"categories": []}', encoding="utf-8")

    source_campaign = CampaignDatabase(name="Source", root=source_root, db_path=db_path)
    bundle_path = tmp_path / "full_bundle.zip"
    export_bundle(bundle_path, source_campaign, selected_records={}, include_database=True)

    target_root = tmp_path / "installed_campaign"
    installed = install_full_campaign_bundle(bundle_path, target_root)

    restored_random_table = installed.root / "static" / "data" / "random_tables" / "encounters.json"
    assert restored_random_table.exists()
    assert restored_random_table.read_text(encoding="utf-8") == '{"categories": []}'


def test_install_full_campaign_bundle_restores_maptools_and_gm_table_files(tmp_path):
    """Installing a full campaign bundle should restore maptools + GM table extra files."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()

    gm_layouts = source_root / "gm_layouts.json"
    gm_layouts.write_text('{"layouts": {"Default": {"tabs": []}}}', encoding="utf-8")

    clue_positions = source_root / "data" / "save" / "clue_positions.json"
    clue_positions.parent.mkdir(parents=True, exist_ok=True)
    clue_positions.write_text('{"Clue A": {"x": 10, "y": 20}}', encoding="utf-8")

    clue_links = source_root / "data" / "save" / "clue_links.json"
    clue_links.write_text('[{"source": "A", "target": "B"}]', encoding="utf-8")

    world_map_data = source_root / "world_maps" / "world_map_data.json"
    world_map_data.parent.mkdir(parents=True, exist_ok=True)
    world_map_data.write_text('{"maps": {"City": {"tokens": []}}}', encoding="utf-8")

    source_campaign = CampaignDatabase(name="Source", root=source_root, db_path=db_path)
    bundle_path = tmp_path / "full_bundle.zip"
    export_bundle(bundle_path, source_campaign, selected_records={}, include_database=True)

    target_root = tmp_path / "installed_campaign"
    installed = install_full_campaign_bundle(bundle_path, target_root)

    restored_gm_layouts = installed.root / "gm_layouts.json"
    restored_clue_positions = installed.root / "data" / "save" / "clue_positions.json"
    restored_clue_links = installed.root / "data" / "save" / "clue_links.json"
    restored_world_map_data = installed.root / "world_maps" / "world_map_data.json"

    assert restored_gm_layouts.exists()
    assert restored_gm_layouts.read_text(encoding="utf-8") == '{"layouts": {"Default": {"tabs": []}}}'
    assert restored_clue_positions.exists()
    assert restored_clue_positions.read_text(encoding="utf-8") == '{"Clue A": {"x": 10, "y": 20}}'
    assert restored_clue_links.exists()
    assert restored_clue_links.read_text(encoding="utf-8") == '[{"source": "A", "target": "B"}]'
    assert restored_world_map_data.exists()
    assert restored_world_map_data.read_text(encoding="utf-8") == '{"maps": {"City": {"tokens": []}}}'


def test_export_bundle_asset_mode_can_include_random_tables_files(tmp_path):
    """Asset bundle exports can optionally include random-table files."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()

    random_tables_file = source_root / "static" / "data" / "random_tables" / "encounters.json"
    random_tables_file.parent.mkdir(parents=True, exist_ok=True)
    random_tables_file.write_text('{"categories": []}', encoding="utf-8")

    source_campaign = CampaignDatabase(name="Source", root=source_root, db_path=db_path)
    bundle_path = tmp_path / "asset_bundle.zip"
    manifest = export_bundle(
        bundle_path,
        source_campaign,
        selected_records={},
        include_database=False,
        include_random_tables=True,
    )

    extra_files = manifest.get("extra_files") or []
    assert any(entry.get("relative_path") == "static/data/random_tables/encounters.json" for entry in extra_files)


def test_apply_import_restores_extra_files_for_asset_bundle(tmp_path):
    """Regular bundle imports should copy bundled extra files like random tables."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()

    random_tables_file = source_root / "static" / "data" / "random_tables" / "encounters.json"
    random_tables_file.parent.mkdir(parents=True, exist_ok=True)
    random_tables_file.write_text('{"categories": []}', encoding="utf-8")

    source_campaign = CampaignDatabase(name="Source", root=source_root, db_path=db_path)
    bundle_path = tmp_path / "asset_bundle.zip"
    export_bundle(
        bundle_path,
        source_campaign,
        selected_records={},
        include_database=False,
        include_random_tables=True,
    )

    target_root = tmp_path / "target"
    target_root.mkdir(parents=True, exist_ok=True)
    target_db = target_root / "campaign.db"
    sqlite3.connect(target_db).close()
    target_campaign = CampaignDatabase(name="Target", root=target_root, db_path=target_db)

    analysis = analyze_bundle(bundle_path, target_campaign.db_path)
    summary = apply_import(analysis, target_campaign, overwrite=True)

    restored = target_root / "static" / "data" / "random_tables" / "encounters.json"
    assert restored.exists()
    assert restored.read_text(encoding="utf-8") == '{"categories": []}'
    assert summary.get("extra_files_imported", 0) >= 1
