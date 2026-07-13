"""Tests for portrait generation configuration helpers."""

from modules.generic.editor.window_components.portrait_generation_dialog import (
    DEFAULT_PORTRAIT_IMAGE_COUNT,
    MAX_PORTRAIT_IMAGE_COUNT,
    MIN_PORTRAIT_IMAGE_COUNT,
    clamp_portrait_image_count,
    get_default_portrait_image_count,
    save_default_portrait_image_count,
)
from modules.helpers.config_helper import ConfigHelper


def test_clamp_portrait_image_count_limits_to_supported_range():
    """Verify portrait candidate counts stay between 1 and 10."""
    assert clamp_portrait_image_count(0) == MIN_PORTRAIT_IMAGE_COUNT
    assert clamp_portrait_image_count(11) == MAX_PORTRAIT_IMAGE_COUNT
    assert clamp_portrait_image_count("bad") == DEFAULT_PORTRAIT_IMAGE_COUNT
    assert clamp_portrait_image_count("8") == 8


def test_portrait_image_count_default_round_trips_to_config(tmp_path):
    """Verify saving a generation count updates the active config default."""
    config_path = tmp_path / "config.ini"
    ConfigHelper._config = None
    ConfigHelper._config_mtime = None
    ConfigHelper._config_path = config_path

    save_default_portrait_image_count(9)

    assert get_default_portrait_image_count() == 9
    assert "image_count = 9" in config_path.read_text(encoding="utf-8")
