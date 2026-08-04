"""Tests for GM Table entity media visibility."""

from modules.scenarios.gm_table.entity_media import has_displayable_entity_image


def test_entity_without_portrait_or_image_has_no_displayable_media(tmp_path) -> None:
    assert not has_displayable_entity_image({"Name": "No Portrait"}, campaign_dir=tmp_path)


def test_entity_with_missing_portrait_has_no_displayable_media(tmp_path) -> None:
    entity = {"Name": "Missing", "Portrait": "portraits/missing.png"}

    assert not has_displayable_entity_image(entity, campaign_dir=tmp_path)


def test_entity_with_existing_image_has_displayable_media(tmp_path) -> None:
    image = tmp_path / "maps" / "location.png"
    image.parent.mkdir()
    image.write_bytes(b"image fixture")

    assert has_displayable_entity_image(
        {"Name": "Location", "Image": "maps/location.png"},
        campaign_dir=tmp_path,
    )
