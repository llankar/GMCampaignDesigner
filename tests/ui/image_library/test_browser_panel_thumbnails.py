"""Regression tests for image browser thumbnail loading."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from modules.ui.image_library import browser_panel as subject


class _FakeCTkImage:
    def __init__(self, *, light_image, dark_image=None, size=None) -> None:
        self.light_image = light_image
        self.dark_image = dark_image
        self.size = size


class _RecordingCache:
    def __init__(self, image: Image.Image) -> None:
        self.image = image
        self.calls: list[tuple[str, tuple[int, int]]] = []

    def get_thumbnail(self, source_path: str, size: tuple[int, int]) -> Image.Image:
        self.calls.append((source_path, size))
        return self.image


class _FailingCache:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, int]]] = []

    def get_thumbnail(self, source_path: str, size: tuple[int, int]) -> Image.Image:
        self.calls.append((source_path, size))
        raise FileNotFoundError(source_path)


def _panel_with_cache(cache):
    panel = subject.ImageBrowserPanel.__new__(subject.ImageBrowserPanel)
    panel._thumbnail_cache = cache
    panel._ctk_images = []
    return panel


def test_load_ctk_thumb_passes_campaign_resolved_path_to_cache(tmp_path, monkeypatch) -> None:
    """Relative campaign asset paths should resolve before thumbnail cache lookup."""
    monkeypatch.setattr(subject.ctk, "CTkImage", _FakeCTkImage)

    campaign_dir = tmp_path / "campaign"
    image_path = campaign_dir / "assets" / "external" / "sample.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(image_path)

    monkeypatch.setattr(subject.ConfigHelper, "get_campaign_dir", staticmethod(lambda: str(campaign_dir)))

    cache_image = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
    cache = _RecordingCache(cache_image)
    panel = _panel_with_cache(cache)

    ctk_image = panel._load_ctk_thumb("assets/external/sample.png", (16, 16))

    assert Path(cache.calls[0][0]) == image_path
    assert cache.calls[0][1] == (16, 16)
    assert ctk_image.light_image is cache_image
    assert panel._ctk_images == [ctk_image]


def test_load_ctk_thumb_uses_placeholder_for_missing_path(tmp_path, monkeypatch) -> None:
    """Missing paths should still produce a CTkImage from the placeholder fallback."""
    monkeypatch.setattr(subject.ctk, "CTkImage", _FakeCTkImage)
    monkeypatch.setattr(subject.ConfigHelper, "get_campaign_dir", staticmethod(lambda: str(tmp_path)))

    cache = _FailingCache()
    panel = _panel_with_cache(cache)

    ctk_image = panel._load_ctk_thumb("assets/external/missing.png", (20, 20))

    assert cache.calls == [(str(Path("assets/external/missing.png").expanduser()), (20, 20))]
    assert ctk_image.size == (20, 20)
    assert ctk_image.light_image.size == (20, 20)
    assert ctk_image.dark_image is ctk_image.light_image
    assert panel._ctk_images == [ctk_image]
