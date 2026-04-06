"""Regression tests for cross campaign asset service."""

import sys
import types

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
