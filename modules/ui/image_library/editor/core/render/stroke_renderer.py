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

        alpha_channel = layer.getchannel("A") if erase else None

        for idx in range(steps + 1):
            t = idx / steps
            x = sx + (ex - sx) * t
            y = sy + (ey - sy) * t
            dab, origin = self._build_dab_mask(x, y, radius, hardness, opacity)
            if erase:
                self._erase(alpha_channel, dab, origin)
            else:
                self._paint(layer, dab, origin, color)
        if erase and alpha_channel is not None:
            layer.putalpha(alpha_channel)

    def _paint(
        self,
        layer: Image.Image,
        dab_mask: Image.Image,
        origin: tuple[int, int],
        color: tuple[int, int, int, int],
    ) -> None:
        brush = Image.new("RGBA", dab_mask.size, color)
        brush.putalpha(dab_mask)
        layer.alpha_composite(brush, dest=origin)

    def _erase(self, alpha_channel: Image.Image | None, dab_mask: Image.Image, origin: tuple[int, int]) -> None:
        if alpha_channel is None:
            return
        left, top = origin
        right = min(alpha_channel.width, left + dab_mask.width)
        bottom = min(alpha_channel.height, top + dab_mask.height)
        if right <= left or bottom <= top:
            return
        alpha_region = alpha_channel.crop((left, top, right, bottom))
        mask_region = dab_mask.crop((0, 0, right - left, bottom - top))
        updated_region = ImageChops.subtract(alpha_region, mask_region)
        alpha_channel.paste(updated_region, (left, top))

    def _build_dab_mask(
        self,
        cx: float,
        cy: float,
        radius: float,
        hardness: float,
        opacity: float,
    ) -> tuple[Image.Image, tuple[int, int]]:
        left = int(math.floor(cx - radius))
        top = int(math.floor(cy - radius))
        right = int(math.ceil(cx + radius))
        bottom = int(math.ceil(cy + radius))
        width = max(1, right - left + 1)
        height = max(1, bottom - top + 1)
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        soft_radius = radius
        inner_radius = radius * hardness
        local_cx = cx - left
        local_cy = cy - top

        if soft_radius <= 1.0:
            draw.point((local_cx, local_cy), fill=int(255 * opacity))
            return mask, (left, top)

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
                (
                    local_cx - current_radius,
                    local_cy - current_radius,
                    local_cx + current_radius,
                    local_cy + current_radius,
                ),
                fill=alpha,
            )
        return mask, (left, top)
