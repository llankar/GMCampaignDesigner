"""Security and portability tests for image-library path references."""

from pathlib import Path

import pytest

from modules.image_assets.paths import (
    InvalidAssetReference,
    make_campaign_relative,
    normalize_asset_reference,
    resolve_asset_reference,
)


def test_reference_round_trip_is_independent_of_working_directory(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    asset = campaign / "assets" / "image_library" / "objects" / "17_xwing.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"image")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    reference = make_campaign_relative(asset, campaign)

    assert reference == "assets/image_library/objects/17_xwing.png"
    assert resolve_asset_reference(reference, campaign) == asset.resolve()


@pytest.mark.parametrize("reference", ["../secret.png", "assets/../secret.png", ""])
def test_resolver_rejects_unsafe_or_empty_references(tmp_path, reference):
    with pytest.raises(InvalidAssetReference):
        resolve_asset_reference(reference, tmp_path)


def test_moved_windows_library_reference_is_read_compatibly(tmp_path):
    assert normalize_asset_reference(
        r"D:\old\campaign\assets\image_library\ships\xwing.png", tmp_path
    ) == "assets/image_library/ships/xwing.png"


def test_arbitrary_external_absolute_reference_is_rejected(tmp_path):
    with pytest.raises(InvalidAssetReference):
        normalize_asset_reference(str(Path("/outside/file.png")), tmp_path)
