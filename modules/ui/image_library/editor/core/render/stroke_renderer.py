"""Raster stroke renderer for circular brush dabs."""

from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageDraw


class StrokeRenderer:
    """Renders brush and eraser strokes onto RGBA layers."""

    def render_stroke(
        self,
        layer: Image.Image,
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        size: float,
        opacity: float,
        hardness: float,
        color: tuple[int, int, int, int],
        erase: bool = False,
    ) -> None:
        radius = max(0.5, float(size) * 0.5)
        hardness = min(1.0, max(0.01, float(hardness)))
        opacity = min(1.0, max(0.0, float(opacity)))
        spacing = max(0.5, radius * 0.35)

        sx, sy = start
        ex, ey = end
        distance = math.dist((sx, sy), (ex, ey))
        steps = max(1, int(distance / spacing))

        for idx in range(steps + 1):
            t = idx / steps
            x = sx + (ex - sx) * t
            y = sy + (ey - sy) * t
            dab = self._build_dab_mask(layer.size, x, y, radius, hardness, opacity)
            if erase:
                self._erase(layer, dab)
            else:
                self._paint(layer, dab, color)

    def _paint(self, layer: Image.Image, dab_mask: Image.Image, color: tuple[int, int, int, int]) -> None:
        brush = Image.new("RGBA", layer.size, color)
        brush.putalpha(dab_mask)
        layer.alpha_composite(brush)

    def _erase(self, layer: Image.Image, dab_mask: Image.Image) -> None:
        channels = list(layer.split())
        channels[3] = ImageChops.subtract(channels[3], dab_mask)
        layer.putalpha(channels[3])

    def _build_dab_mask(
        self,
        size: tuple[int, int],
        cx: float,
        cy: float,
        radius: float,
        hardness: float,
        opacity: float,
    ) -> Image.Image:
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        soft_radius = radius
        inner_radius = radius * hardness

        if soft_radius <= 1.0:
            draw.point((cx, cy), fill=int(255 * opacity))
            return mask

        # Soft falloff built with concentric circles.
        rings = max(4, int(radius))
        for ring in range(rings, -1, -1):
            t = ring / rings
            current_radius = soft_radius * t
            if current_radius <= inner_radius:
                alpha = int(255 * opacity)
            else:
                fade = (soft_radius - current_radius) / max(0.001, soft_radius - inner_radius)
                alpha = int(255 * opacity * max(0.0, min(1.0, fade)))
            if alpha <= 0:
                continue
            draw.ellipse(
                (cx - current_radius, cy - current_radius, cx + current_radius, cy + current_radius),
                fill=alpha,
            )
        return mask
