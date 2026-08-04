"""Tests for entity-detail portrait cropping."""

from modules.generic.detail_ui import portrait_fitting


def test_portrait_crop_is_anchored_to_top(monkeypatch) -> None:
    captured = {}
    expected = object()

    def fake_fit(image, size, *, method, centering):
        captured.update(
            image=image,
            size=size,
            method=method,
            centering=centering,
        )
        return expected

    monkeypatch.setattr(portrait_fitting.ImageOps, "fit", fake_fit, raising=False)
    source = object()

    result = portrait_fitting.fit_portrait_to_frame(source, (320, 420))

    assert result is expected
    assert captured == {
        "image": source,
        "size": (320, 420),
        "method": portrait_fitting.Image.Resampling.LANCZOS,
        "centering": (0.5, 0.0),
    }
