"""Layer compositor for image-editor previews and export."""

from __future__ import annotations

from PIL import Image

from modules.ui.image_library.editor.core.layer import Layer


def flatten_layers(width: int, height: int, layers: list[Layer]) -> Image.Image:
    """Composites all visible layers into a flattened RGBA image."""

    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for layer in layers:
        if not layer.visible:
            continue
        rgba = layer.image.convert("RGBA")
        opacity = max(0.0, min(1.0, float(layer.opacity)))
        if opacity < 1.0:
            channels = list(rgba.split())
            channels[3] = channels[3].point(lambda alpha: int(alpha * opacity))
            rgba = Image.merge("RGBA", channels)
        # Future blend modes can be handled here; currently defaults to normal alpha composite.
        result.alpha_composite(rgba)
    return result
