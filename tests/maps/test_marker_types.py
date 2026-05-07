from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from modules.maps.controllers.display_map_controller import DisplayMapController
from modules.maps.marker_types import (
    DEFAULT_MARKER_TYPE,
    MARKER_TYPES,
    MARKER_TYPE_LABELS,
    marker_type_color,
    marker_type_icon_path,
    marker_type_label,
    normalize_marker_type,
)
from modules.maps.world_map_view import WorldMapPanel


EXPECTED_MARKER_ICON_PATHS = {
    "note": "assets/icons/marker_note.png",
    "location": "assets/icons/marker_location.png",
    "danger": "assets/icons/marker_danger.png",
    "treasure": "assets/icons/marker_treasure.png",
    "quest": "assets/icons/marker_quest.png",
}


def test_marker_type_defaults_are_backward_compatible():
    assert normalize_marker_type(None) == DEFAULT_MARKER_TYPE
    assert normalize_marker_type("") == DEFAULT_MARKER_TYPE
    assert marker_type_label({}) == "Note"


def test_marker_type_accepts_keys_and_labels():
    assert normalize_marker_type("danger") == "danger"
    assert normalize_marker_type("Treasure") == "treasure"
    assert normalize_marker_type("Unknown") == DEFAULT_MARKER_TYPE


def test_marker_type_metadata_has_assets_and_colors():
    project_root = Path(__file__).resolve().parents[2]
    assert {
        marker_type.key: marker_type.icon_path
        for marker_type in MARKER_TYPES
    } == EXPECTED_MARKER_ICON_PATHS

    for label in MARKER_TYPE_LABELS:
        marker_type = normalize_marker_type(label)
        icon_path = marker_type_icon_path(marker_type)
        assert icon_path.endswith(".png")
        assert (project_root / icon_path).is_file()
        assert marker_type_color(marker_type).startswith("#")


def _foreground_glyph_mask(image):
    """Return a stable mask for the glyph area, ignoring marker pin color."""
    resized = image.convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
    crop = resized.crop((10, 7, 38, 34))
    visible_colors = []

    for red, green, blue, alpha in crop.getdata():
        luminance = (red + green + blue) / 3
        if alpha > 32 and luminance > 80:
            visible_colors.append((red, green, blue))

    color_buckets = Counter(
        (red // 16, green // 16, blue // 16)
        for red, green, blue in visible_colors
    )
    background_bucket = color_buckets.most_common(1)[0][0]
    background_color = tuple(channel * 16 + 8 for channel in background_bucket)
    glyph_pixels = []

    for red, green, blue, alpha in crop.getdata():
        luminance = (red + green + blue) / 3
        color_distance = sum(
            (value - background) ** 2
            for value, background in zip((red, green, blue), background_color)
        ) ** 0.5
        glyph_pixels.append(alpha > 32 and luminance > 115 and color_distance > 45)

    return tuple(glyph_pixels)


def test_marker_type_icons_have_distinct_glyph_shapes():
    project_root = Path(__file__).resolve().parents[2]
    glyph_masks = {}

    for label in MARKER_TYPE_LABELS:
        marker_type = normalize_marker_type(label)
        icon_path = project_root / marker_type_icon_path(marker_type)
        with Image.open(icon_path) as image:
            assert image.size == (96, 96)
            assert image.mode == "RGBA"
            glyph_masks[marker_type] = _foreground_glyph_mask(image)
        assert sum(glyph_masks[marker_type]) >= 100

    assert len(set(glyph_masks.values())) == len(MARKER_TYPE_LABELS)


def test_display_marker_filter_defaults_missing_type_to_note():
    controller = SimpleNamespace(marker_type_filter="Note")

    assert DisplayMapController._marker_matches_filter(controller, {}) is True

    controller.marker_type_filter = "Danger"
    assert DisplayMapController._marker_matches_filter(controller, {"marker_type": "danger"}) is True
    assert DisplayMapController._marker_matches_filter(controller, {}) is False


def test_world_map_marker_filter_defaults_missing_type_to_note():
    panel = SimpleNamespace(marker_type_filter="Note")

    assert WorldMapPanel._marker_matches_filter(panel, {}) is True

    panel.marker_type_filter = "Treasure"
    assert WorldMapPanel._marker_matches_filter(panel, {"marker_type": "Treasure"}) is True
    assert WorldMapPanel._marker_matches_filter(panel, {"marker_type": "danger"}) is False


def test_display_marker_filter_cleanup_deletes_canvas_items_and_widgets():
    class FakeCanvas:
        def __init__(self):
            self.deleted = []

        def delete(self, cid):
            self.deleted.append(cid)

    class FakeWidget:
        def __init__(self):
            self.destroyed = False

        def winfo_exists(self):
            return True

        def destroy(self):
            self.destroyed = True

    canvas = FakeCanvas()
    entry_widget = FakeWidget()
    handle_widget = FakeWidget()
    hidden_descriptions = []
    controller = SimpleNamespace(
        canvas=canvas,
        _hide_marker_description=lambda marker: hidden_descriptions.append(marker),
    )
    marker = {
        "entry_canvas_id": 10,
        "handle_canvas_id": 11,
        "border_canvas_id": 12,
        "canvas_ids": (10, 11, 12),
        "entry_widget": entry_widget,
        "handle_widget": handle_widget,
    }

    DisplayMapController._clear_marker_render_artifacts(controller, marker)

    assert canvas.deleted == [10, 11, 12]
    assert entry_widget.destroyed is True
    assert handle_widget.destroyed is True
    assert marker["canvas_ids"] == ()
    assert marker["entry_canvas_id"] is None
    assert marker["handle_canvas_id"] is None
    assert marker["border_canvas_id"] is None
    assert marker["entry_widget"] is None
    assert marker["handle_widget"] is None
    assert hidden_descriptions == [marker]
