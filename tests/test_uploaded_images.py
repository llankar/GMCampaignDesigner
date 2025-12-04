from io import BytesIO
from pathlib import Path

from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.whiteboard.utils.uploaded_images import save_uploaded_image


class _FakeFileStorage:
    def __init__(self, filename: str, stream: BytesIO):
        self.filename = filename
        self.stream = stream


def test_save_uploaded_image_handles_jpeg(tmp_path, monkeypatch):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()

    monkeypatch.setattr(ConfigHelper, "get_campaign_dir", lambda: str(campaign_dir))

    image = Image.new("RGB", (10, 20), color=(255, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)

    file_storage = _FakeFileStorage("test.jpg", buffer)

    saved = save_uploaded_image(file_storage)

    destination = Path(saved.path)
    assert destination.exists()

    with Image.open(destination) as saved_image:
        assert saved_image.mode == "RGB"
        assert saved_image.size == (10, 20)
