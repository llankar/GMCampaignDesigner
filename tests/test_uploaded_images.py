from io import BytesIO
from pathlib import Path

from modules.helpers.config_helper import ConfigHelper
import modules.whiteboard.utils.uploaded_images as uploaded_images
from modules.whiteboard.utils.uploaded_images import save_uploaded_image


class _FakeFileStorage:
    def __init__(self, filename: str, stream: BytesIO):
        self.filename = filename
        self.stream = stream


class _FakeImage:
    def __init__(self, mode="RGB", size=(10, 20)):
        self.mode = mode
        self.size = size

    def convert(self, mode):
        self.mode = mode
        return self

    def save(self, destination):
        Path(destination).write_bytes(b"img")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_save_uploaded_image_handles_jpeg(tmp_path, monkeypatch):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()

    monkeypatch.setattr(ConfigHelper, "get_campaign_dir", lambda: str(campaign_dir))
    monkeypatch.setattr(uploaded_images.Image, "open", lambda *_args, **_kwargs: _FakeImage())

    file_storage = _FakeFileStorage("test.jpg", BytesIO(b"fake"))

    saved = save_uploaded_image(file_storage)

    destination = Path(saved.path)
    assert destination.exists()
    assert saved.width == 10
    assert saved.height == 20
