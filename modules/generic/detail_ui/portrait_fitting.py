"""Portrait-specific image fitting helpers for entity detail views."""

from __future__ import annotations

from PIL import Image, ImageOps


PORTRAIT_CROP_CENTERING = (0.5, 0.0)


def fit_portrait_to_frame(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Fill a portrait frame while preserving the top of oversized images."""
    return ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=PORTRAIT_CROP_CENTERING,
    )
