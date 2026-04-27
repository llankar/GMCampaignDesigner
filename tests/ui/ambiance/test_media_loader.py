from modules.ui.ambiance.media_loader import infer_media_type, normalize_item
from modules.ui.ambiance.models import AmbianceItem


def test_infer_media_type_from_extensions():
    assert infer_media_type("scene.jpg") == "image"
    assert infer_media_type("loop.mp4") == "video"


def test_normalize_item_applies_default_duration():
    item = AmbianceItem(path="scene.png", media_type="image", duration=0)

    normalized = normalize_item(item, default_duration=6.5)

    assert normalized.duration == 6.5
