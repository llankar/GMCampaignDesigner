"""Document model for the image editor core."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass
class ImageDocument:
    """Stores editable RGBA layers and active-layer metadata."""

    width: int
    height: int
    layers: list[Image.Image]
    active_layer_index: int = 0

    @classmethod
    def from_image(cls, image: Image.Image) -> "ImageDocument":
        rgba = image.convert("RGBA")
        return cls(width=rgba.width, height=rgba.height, layers=[rgba])

    @property
    def active_layer(self) -> Image.Image:
        return self.layers[self.active_layer_index]

    def composite(self) -> Image.Image:
        result = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        for layer in self.layers:
            result.alpha_composite(layer)
        return result

    def reset_from(self, image: Image.Image) -> None:
        rgba = image.convert("RGBA")
        self.width = rgba.width
        self.height = rgba.height
        self.layers = [rgba]
        self.active_layer_index = 0

    def rotate(self, degrees: int) -> None:
        self.layers = [layer.rotate(-degrees, expand=True) for layer in self.layers]
        self.width, self.height = self.layers[0].size

    def mirror(self) -> None:
        self.layers = [ImageOps.mirror(layer) for layer in self.layers]

    def flip(self) -> None:
        self.layers = [ImageOps.flip(layer) for layer in self.layers]
