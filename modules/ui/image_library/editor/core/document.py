"""Document model for the image editor core."""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageOps

from modules.ui.image_library.editor.core.compositor import flatten_layers
from modules.ui.image_library.editor.core.layer import Layer


@dataclass
class ImageDocument:
    """Stores editable RGBA layers and active-layer metadata."""

    width: int
    height: int
    layers: list[Layer] = field(default_factory=list)
    active_layer_index: int = 0

    @classmethod
    def from_image(cls, image: Image.Image) -> "ImageDocument":
        rgba = image.convert("RGBA")
        return cls(
            width=rgba.width,
            height=rgba.height,
            layers=[Layer(name="Background", visible=True, opacity=1.0, blend_mode="normal", image=rgba)],
            active_layer_index=0,
        )

    @property
    def active_layer(self) -> Image.Image:
        return self.layers[self.active_layer_index].image

    def composite(self) -> Image.Image:
        return flatten_layers(self.width, self.height, self.layers)

    def add_layer(self, name: str | None = None) -> int:
        layer_name = name or f"Layer {len(self.layers) + 1}"
        blank = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self.layers.append(Layer(name=layer_name, visible=True, opacity=1.0, blend_mode="normal", image=blank))
        self.active_layer_index = len(self.layers) - 1
        return self.active_layer_index

    def delete_active_layer(self) -> bool:
        if len(self.layers) <= 1:
            return False
        self.layers.pop(self.active_layer_index)
        self.active_layer_index = max(0, min(self.active_layer_index, len(self.layers) - 1))
        return True

    def move_active_layer(self, direction: int) -> bool:
        target_index = self.active_layer_index + direction
        if target_index < 0 or target_index >= len(self.layers):
            return False
        self.layers[self.active_layer_index], self.layers[target_index] = self.layers[target_index], self.layers[self.active_layer_index]
        self.active_layer_index = target_index
        return True

    def set_active_layer(self, index: int) -> bool:
        if index < 0 or index >= len(self.layers):
            return False
        self.active_layer_index = index
        return True

    def toggle_layer_visibility(self, index: int) -> bool:
        if index < 0 or index >= len(self.layers):
            return False
        layer = self.layers[index]
        layer.visible = not layer.visible
        return True

    def reset_from(self, image: Image.Image) -> None:
        rgba = image.convert("RGBA")
        self.width = rgba.width
        self.height = rgba.height
        self.layers = [Layer(name="Background", visible=True, opacity=1.0, blend_mode="normal", image=rgba)]
        self.active_layer_index = 0

    def rotate(self, degrees: int) -> None:
        for layer in self.layers:
            layer.image = layer.image.rotate(-degrees, expand=True)
        self.width, self.height = self.layers[0].image.size

    def mirror(self) -> None:
        for layer in self.layers:
            layer.image = ImageOps.mirror(layer.image)

    def flip(self) -> None:
        for layer in self.layers:
            layer.image = ImageOps.flip(layer.image)
