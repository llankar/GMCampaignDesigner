"""Regression tests for cross campaign asset service."""

import shutil
import sqlite3
import sys
import types
import zipfile

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

from modules.ui.ambiance.library.index_store import CampaignWallpaperIndexStore
from modules.ui.ambiance.library.models import WallpaperLibraryItem

from modules.generic.cross_campaign_asset_service import (
    CampaignDatabase,
    _rewrite_record_paths,
    collect_assets,
    export_bundle,
    install_full_campaign_bundle,
    analyze_bundle,
    apply_import,
)


def test_analyze_bundle_rejects_unsafe_zip_member_path(tmp_path):
    """Bundle extraction should reject zip members that escape the extraction root."""
    bundle_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr("manifest.json", '{"version": 1}')
        zf.writestr("../escape.txt", "nope")

    with pytest.raises(ValueError, match="Unsafe bundle member path"):
        analyze_bundle(bundle_path, tmp_path / "target.db")

    assert not (tmp_path / "escape.txt").exists()


def test_analyze_bundle_ignores_unsafe_or_malformed_ambiance_wallpaper_entries(tmp_path):
    """Wallpaper bundle metadata should sanitize relative paths and tolerate malformed numbers."""
    bundle_path = tmp_path / "wallpapers.zip"
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"version": 1, "ambiance_wallpapers": {"index_path": "ambiance_wallpapers/index.json"}}',
        )
        zf.writestr(
            "ambiance_wallpapers/index.json",
            (
                '{"items": ['
                '{"id": "safe", "relative_path": "nested/sky.png", "filename": "sky.png", '
                '"created_at": "not-a-float"},'
                '{"id": "unsafe", "relative_path": "../escape.png", "filename": "escape.png"}'
                ']}'
            ),
        )

    analysis = analyze_bundle(bundle_path, tmp_path / "target.db")
    try:
        assert analysis.ambiance_wallpapers == [
            {
                "id": "safe",
                "relative_path": "nested/sky.png",
                "filename": "sky.png",
                "media_type": "image",
                "width": None,
                "height": None,
                "filesize": 0,
                "created_at": 0.0,
                "tags": [],
            }
        ]
    finally:
        shutil.rmtree(analysis.temp_dir, ignore_errors=True)


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


def test_villain_assets_collect_and_rewrite_portrait_and_audio(tmp_path):
    """Villains should export and import both portrait and audio media paths."""
    campaign_root = tmp_path / "campaign"
    portrait_path = "portraits/villains/lich.png"
    audio_path = "audio/villains/lich_theme.mp3"
    portrait_file = campaign_root / portrait_path
    audio_file = campaign_root / audio_path
    portrait_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    portrait_file.write_bytes(b"portrait-bytes")
    audio_file.write_bytes(b"audio-bytes")
    record = {
        "Name": "The Ashen Lich",
        "Portrait": portrait_path,
        "Audio": audio_path,
    }

    assets = collect_assets("villains", [record], campaign_root)

    assets_by_type = {asset.asset_type: asset for asset in assets}
    assert set(assets_by_type) == {"portrait", "audio"}
    assert assets_by_type["portrait"].original_path == portrait_path
    assert assets_by_type["portrait"].absolute_path == portrait_file.resolve()
    assert assets_by_type["audio"].original_path == audio_path
    assert assets_by_type["audio"].absolute_path == audio_file.resolve()

    updated = _rewrite_record_paths(
        "villains",
        record,
        {
            portrait_path: "assets/portraits/villains/lich.png",
            audio_path: "assets/audio/villains/lich_theme.mp3",
        },
    )

    assert updated["Portrait"] == "assets/portraits/villains/lich.png"
    assert updated["Audio"] == "assets/audio/villains/lich_theme.mp3"


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


def test_export_bundle_full_campaign_keeps_explicit_selections(tmp_path, monkeypatch):
    """Explicitly selected entity lists should not be replaced by full-campaign backfill."""
    campaign_root = tmp_path / "source_campaign"
    campaign_root.mkdir(parents=True, exist_ok=True)
    db_path = campaign_root / "campaign.db"
    sqlite3.connect(db_path).close()

    selected_villain = {"Name": "Selected Villain"}
    loaded_types = []

    def fake_load_entities(entity_type, _db_path):
        loaded_types.append(entity_type)
        if entity_type == "villains":
            return [{"Name": "Database Villain"}]
        if entity_type == "campaigns":
            return [{"Name": "Loaded Campaign"}]
        return []

    monkeypatch.setattr(
        "modules.generic.cross_campaign_asset_service.list_known_entities",
        lambda: ["villains", "campaigns"],
    )
    monkeypatch.setattr("modules.generic.cross_campaign_asset_service.load_entities", fake_load_entities)

    manifest = export_bundle(
        tmp_path / "bundle.zip",
        CampaignDatabase(name="Source", root=campaign_root, db_path=db_path),
        selected_records={"villains": [selected_villain]},
        include_database=True,
    )

    assert loaded_types == ["campaigns"]
    assert manifest["entities"]["villains"]["count"] == 1
    assert manifest["entities"]["campaigns"]["count"] == 1

    with zipfile.ZipFile(tmp_path / "bundle.zip", "r") as zf:
        villains = zf.read("data/villains.json").decode("utf-8")
    assert "Selected Villain" in villains
    assert "Database Villain" not in villains


def test_export_bundle_full_campaign_skips_missing_backfill_tables(tmp_path, monkeypatch):
    """Missing tables during full-campaign backfill should not stop later entity types."""
    campaign_root = tmp_path / "source_campaign"
    campaign_root.mkdir(parents=True, exist_ok=True)
    db_path = campaign_root / "campaign.db"
    sqlite3.connect(db_path).close()

    loaded_types = []

    def fake_load_entities(entity_type, _db_path):
        loaded_types.append(entity_type)
        if entity_type == "missing_entities":
            raise sqlite3.OperationalError("no such table: missing_entities")
        if entity_type == "campaigns":
            return [{"Name": "Loaded Campaign"}]
        return []

    monkeypatch.setattr(
        "modules.generic.cross_campaign_asset_service.list_known_entities",
        lambda: ["missing_entities", "campaigns"],
    )
    monkeypatch.setattr("modules.generic.cross_campaign_asset_service.load_entities", fake_load_entities)

    manifest = export_bundle(
        tmp_path / "bundle.zip",
        CampaignDatabase(name="Source", root=campaign_root, db_path=db_path),
        selected_records={},
        include_database=True,
    )

    assert loaded_types == ["missing_entities", "campaigns"]
    assert "missing_entities" not in manifest["entities"]
    assert manifest["entities"]["campaigns"]["count"] == 1


def test_export_bundle_full_campaign_loads_all_known_entities_and_villain_media(tmp_path, monkeypatch):
    """Full campaign exports should backfill every known entity type and villain media."""
    campaign_root = tmp_path / "source_campaign"
    campaign_root.mkdir(parents=True, exist_ok=True)
    db_path = campaign_root / "campaign.db"
    sqlite3.connect(db_path).close()

    image_file = campaign_root / "assets" / "image_library" / "tiles" / "forest.png"
    portrait_file = campaign_root / "portraits" / "villains" / "lich.png"
    audio_file = campaign_root / "audio" / "villains" / "lich_theme.mp3"
    for media_file, content in (
        (image_file, b"forest-bytes"),
        (portrait_file, b"portrait-bytes"),
        (audio_file, b"audio-bytes"),
    ):
        media_file.parent.mkdir(parents=True, exist_ok=True)
        media_file.write_bytes(content)

    records_by_type = {
        "villains": [
            {
                "Name": "The Ashen Lich",
                "Portrait": "portraits/villains/lich.png",
                "Audio": "audio/villains/lich_theme.mp3",
            }
        ],
        "campaigns": [{"Name": "Embers of Dusk"}],
        "scenarios": [{"Name": "The First Spark"}],
        "image_assets": [{"Name": "Forest Tile", "RelativePath": "assets/image_library/tiles/forest.png"}],
        "maps": [{"Name": "Cavern"}],
    }

    def fake_load_entities(entity_type, _db_path):
        return records_by_type.get(entity_type, [])

    monkeypatch.setattr(
        "modules.generic.cross_campaign_asset_service.list_known_entities",
        lambda: ["villains", "campaigns", "scenarios", "image_assets", "maps"],
    )
    monkeypatch.setattr("modules.generic.cross_campaign_asset_service.load_entities", fake_load_entities)

    manifest = export_bundle(
        tmp_path / "bundle.zip",
        CampaignDatabase(name="Source", root=campaign_root, db_path=db_path),
        selected_records={},
        include_database=True,
    )

    for entity_type in ("villains", "campaigns", "scenarios", "image_assets", "maps"):
        assert manifest["entities"][entity_type]["count"] == 1

    villain_assets = {
        asset["asset_type"]: asset
        for asset in manifest["assets"]
        if asset["entity_type"] == "villains" and asset["record_key"] == "The Ashen Lich"
    }
    assert villain_assets["portrait"]["original_path"] == "portraits/villains/lich.png"
    assert villain_assets["audio"]["original_path"] == "audio/villains/lich_theme.mp3"

    with zipfile.ZipFile(tmp_path / "bundle.zip", "r") as zf:
        names = set(zf.namelist())
    assert "assets/portraits/villains/lich.png" in names
    assert "assets/audio/villains/lich_theme.mp3" in names


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


def test_install_full_campaign_bundle_restores_campaign_custom_random_tables_file(tmp_path):
    """Installing a full campaign bundle should restore campaign custom random tables JSON."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()

    campaign_custom_file = source_root / "campaign_custom_tables.json"
    campaign_custom_file.write_text('{"tables": []}', encoding="utf-8")

    source_campaign = CampaignDatabase(name="Source", root=source_root, db_path=db_path)
    bundle_path = tmp_path / "full_bundle.zip"
    manifest = export_bundle(bundle_path, source_campaign, selected_records={}, include_database=True)
    extra_files = manifest.get("extra_files") or []
    assert any(entry.get("relative_path") == "campaign_custom_tables.json" for entry in extra_files)

    target_root = tmp_path / "installed_campaign"
    installed = install_full_campaign_bundle(bundle_path, target_root)

    restored_campaign_custom = installed.root / "campaign_custom_tables.json"
    assert restored_campaign_custom.exists()
    assert restored_campaign_custom.read_text(encoding="utf-8") == '{"tables": []}'


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


def _write_wallpaper(campaign_root, relative_path="nested/sky.png", content=b"sky"):
    store = CampaignWallpaperIndexStore(str(campaign_root))
    media = store.wallpapers_dir / relative_path
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(content)
    item = WallpaperLibraryItem(
        id="wall-1",
        relative_path=relative_path,
        filename=media.name,
        media_type="image",
        width=1920,
        height=1080,
        filesize=len(content),
        created_at=123.0,
        tags=("night", "forest"),
    )
    store.save([item])
    return item, media


def test_export_bundle_includes_ambiance_wallpaper_files_and_metadata(tmp_path):
    """Ambiance wallpaper media and index metadata should be bundled separately."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()
    item, _media = _write_wallpaper(source_root)

    source_campaign = CampaignDatabase(name="Source", root=source_root, db_path=db_path)
    bundle_path = tmp_path / "wallpapers.zip"

    manifest = export_bundle(bundle_path, source_campaign, selected_records={}, include_database=False)

    section = manifest["ambiance_wallpapers"]
    assert section["count"] == 1
    assert section["items"][0]["id"] == item.id
    assert section["items"][0]["relative_path"] == item.relative_path
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = set(zf.namelist())
    assert "ambiance_wallpapers/index.json" in names
    assert "ambiance_wallpapers/files/nested/sky.png" in names


def test_apply_import_restores_ambiance_wallpaper_media_and_index(tmp_path):
    """Regular imports should restore wallpaper files and merge the target index."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()
    item, _media = _write_wallpaper(source_root)
    bundle_path = tmp_path / "wallpapers.zip"
    export_bundle(bundle_path, CampaignDatabase("Source", source_root, db_path), {}, include_database=False)

    target_root = tmp_path / "target"
    target_root.mkdir(parents=True, exist_ok=True)
    target_db = target_root / "campaign.db"
    sqlite3.connect(target_db).close()
    target_campaign = CampaignDatabase("Target", target_root, target_db)

    analysis = analyze_bundle(bundle_path, target_campaign.db_path)
    assert analysis.ambiance_wallpapers[0]["relative_path"] == item.relative_path
    summary = apply_import(analysis, target_campaign, overwrite=False)

    target_store = CampaignWallpaperIndexStore(str(target_root))
    restored = target_store.wallpapers_dir / item.relative_path
    assert restored.read_bytes() == b"sky"
    assert target_store.load()[0].tags == item.tags
    assert summary["ambiance_wallpapers_imported"] == 1
    assert summary["ambiance_wallpapers_updated"] == 0
    assert summary["ambiance_wallpapers_skipped"] == 0


def test_apply_import_skips_or_overwrites_existing_ambiance_wallpapers(tmp_path):
    """Wallpaper import duplicates should match by relative_path or id and honor overwrite."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()
    item, _media = _write_wallpaper(source_root, content=b"new")
    bundle_path = tmp_path / "wallpapers.zip"
    export_bundle(bundle_path, CampaignDatabase("Source", source_root, db_path), {}, include_database=False)

    target_root = tmp_path / "target"
    target_root.mkdir(parents=True, exist_ok=True)
    target_db = target_root / "campaign.db"
    sqlite3.connect(target_db).close()
    target_store = CampaignWallpaperIndexStore(str(target_root))
    existing_media = target_store.wallpapers_dir / item.relative_path
    existing_media.parent.mkdir(parents=True, exist_ok=True)
    existing_media.write_bytes(b"old")
    target_store.save([
        WallpaperLibraryItem(
            id="existing-id",
            relative_path=item.relative_path,
            filename=item.filename,
            media_type="image",
            width=100,
            height=100,
            filesize=3,
            created_at=1.0,
            tags=("old",),
        )
    ])
    target_campaign = CampaignDatabase("Target", target_root, target_db)

    skip_summary = apply_import(analyze_bundle(bundle_path, target_db), target_campaign, overwrite=False)
    assert existing_media.read_bytes() == b"old"
    assert target_store.load()[0].id == "existing-id"
    assert skip_summary["ambiance_wallpapers_skipped"] == 1

    overwrite_summary = apply_import(analyze_bundle(bundle_path, target_db), target_campaign, overwrite=True)
    loaded = target_store.load()
    assert existing_media.read_bytes() == b"new"
    assert len(loaded) == 1
    assert loaded[0].id == item.id
    assert loaded[0].tags == item.tags
    assert overwrite_summary["ambiance_wallpapers_updated"] == 1


def test_install_full_campaign_bundle_restores_ambiance_wallpapers(tmp_path):
    """Full campaign installation should restore ambiance wallpaper files and index."""
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    db_path = source_root / "campaign.db"
    sqlite3.connect(db_path).close()
    item, _media = _write_wallpaper(source_root)
    bundle_path = tmp_path / "full_wallpapers.zip"
    export_bundle(bundle_path, CampaignDatabase("Source", source_root, db_path), {}, include_database=True)

    installed = install_full_campaign_bundle(bundle_path, tmp_path / "installed")

    store = CampaignWallpaperIndexStore(str(installed.root))
    assert (store.wallpapers_dir / item.relative_path).read_bytes() == b"sky"
    assert store.load()[0].id == item.id
