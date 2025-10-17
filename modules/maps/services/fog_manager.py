import math
import random

from PIL import ImageChops, ImageDraw, Image, ImageFilter, ImageTk
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def _mask_to_brush(mask: Image.Image) -> Image.Image:
    """Convert an ``L`` mask into a semi-transparent RGBA brush."""
    alpha = mask.point(lambda a: int(min(128, round(a * 128 / 255))))
    brush = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    brush.putalpha(alpha)
    return brush


def _create_cloud_mask(size: int, rng: random.Random) -> Image.Image:
    size = max(4, int(size))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    cx = size / 2.0
    cy = size / 2.0
    base_radius = size * rng.uniform(0.28, 0.42)
    draw.ellipse((cx - base_radius, cy - base_radius, cx + base_radius, cy + base_radius), fill=rng.randint(120, 200))

    lobe_count = rng.randint(6, 9)
    lobe_count += max(0, size // 30)
    for _ in range(lobe_count):
        angle = rng.uniform(0.0, math.tau)
        distance = rng.uniform(0.0, size * 0.25)
        stretch = rng.uniform(0.75, 1.2)
        rx = size * rng.uniform(0.18, 0.45)
        ry = rx * rng.uniform(0.7, 1.1)
        ox = cx + math.cos(angle) * distance
        oy = cy + math.sin(angle) * distance * stretch
        draw.ellipse((ox - rx, oy - ry, ox + rx, oy + ry), fill=rng.randint(100, 255))

    blur_radius = max(2, int(size * 0.22))
    return mask.filter(ImageFilter.GaussianBlur(blur_radius))


def _create_radial_mask(size: int) -> Image.Image:
    size = max(4, int(size))
    mask = Image.new("L", (size, size), 0)
    pixels = mask.load()
    cx = (size - 1) / 2.0
    cy = (size - 1) / 2.0
    max_dist = max(1e-6, math.hypot(cx, cy))
    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - cx, y - cy)
            ratio = max(0.0, 1.0 - dist / max_dist)
            pixels[x, y] = int((ratio ** 1.6) * 255)
    blur_radius = max(1, int(size * 0.12))
    return mask.filter(ImageFilter.GaussianBlur(blur_radius))


def _create_soft_square_mask(size: int) -> Image.Image:
    size = max(4, int(size))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    padding = size * 0.08
    draw.rectangle((padding, padding, size - padding, size - padding), fill=255)
    blur_radius = max(1, int(size * 0.12))
    return mask.filter(ImageFilter.GaussianBlur(blur_radius))


def _acquire_fog_brush(self, size: int, shape: str) -> Image.Image | None:
    size = max(4, int(size))
    shape_key = (shape or "cloud").lower()
    cache = getattr(self, "_fog_brush_cache", None)
    if cache is None:
        cache = {}
        self._fog_brush_cache = cache

    entry = cache.get((shape_key, size))
    if not entry:
        rng_seed = getattr(self, "_fog_brush_seed", None)
        if rng_seed is None:
            rng_seed = random.randrange(1 << 30)
            self._fog_brush_seed = rng_seed
        rng = random.Random((rng_seed ^ (size << 7) ^ hash(shape_key)) & 0xFFFFFFFF)

        if shape_key == "rectangle":
            variants = [_mask_to_brush(_create_soft_square_mask(size))]
        elif shape_key == "circle":
            variants = [_mask_to_brush(_create_radial_mask(size))]
        else:
            variants = [_mask_to_brush(_create_cloud_mask(size, rng)) for _ in range(4)]

        entry = {"variants": variants, "index": 0}
        cache[(shape_key, size)] = entry

    variants = entry.get("variants") or []
    if not variants:
        return None
    index = entry.get("index", 0) % len(variants)
    entry["index"] = (index + 1) % len(variants)
    return variants[index]


def _apply_fog_brush(self, brush: Image.Image, left: int, top: int, mode: str) -> None:
    if brush is None or self.mask_img is None:
        return

    bw, bh = brush.size
    width, height = self.mask_img.size
    region_box = (
        max(0, left),
        max(0, top),
        min(width, left + bw),
        min(height, top + bh),
    )
    if region_box[0] >= region_box[2] or region_box[1] >= region_box[3]:
        return

    brush_box = (
        region_box[0] - left,
        region_box[1] - top,
        region_box[0] - left + (region_box[2] - region_box[0]),
        region_box[1] - top + (region_box[3] - region_box[1]),
    )
    brush_crop = brush.crop(brush_box)
    region = self.mask_img.crop(region_box).convert("RGBA")

    existing_alpha = region.split()[3]
    brush_alpha = brush_crop.getchannel("A")
    if mode == "add":
        new_alpha = ImageChops.lighter(existing_alpha, brush_alpha)
    else:
        new_alpha = ImageChops.subtract(existing_alpha, brush_alpha)

    updated_region = Image.new("RGBA", region.size, (0, 0, 0, 0))
    updated_region.putalpha(new_alpha)
    self.mask_img.paste(updated_region, region_box)

def _set_fog(self, mode):
    """Toggle the active fog brush mode between add/remove/none."""
    if mode not in ("add", "rem"):
        new_mode = None
    else:
        current = getattr(self, "fog_mode", None)
        new_mode = None if current == mode else mode

    self.fog_mode = new_mode

    updater = getattr(self, "_update_fog_button_states", None)
    if callable(updater):
        updater()

def clear_fog(self):
    self.mask_img = Image.new("RGBA", self.base_img.size, (0,0,0,0))
    self._update_canvas_images()

def reset_fog(self):
    self.mask_img = Image.new("RGBA", self.base_img.size, (0, 0, 0, 128))
    self._update_canvas_images()

def on_paint(self, event):
    """Paint or erase fog using a soft brush for cloud-like masks."""
    if self.fog_mode not in ("add", "rem"):
        return
    if any('drag_data' in t for t in self.tokens):
        return
    if not self.mask_img:
        return

    # Convert screen → world coords
    xw = (event.x - self.pan_x) / self.zoom
    yw = (event.y - self.pan_y) / self.zoom

    brush_size = max(4, int(getattr(self, "brush_size", 32)))
    shape = getattr(self, "brush_shape", "cloud") or "cloud"
    brush = _acquire_fog_brush(self, brush_size, shape)
    if brush is None:
        return

    left = int(round(xw - brush.width / 2))
    top = int(round(yw - brush.height / 2))
    mode = "add" if self.fog_mode == "add" else "rem"
    _apply_fog_brush(self, brush, left, top, mode)

    # —— only resize & blit the mask ——
    w, h = self.base_img.size
    sw, sh = int(w * self.zoom), int(h * self.zoom)

    # use the interactive (fast) filter
    mask_resized = self.mask_img.resize((sw, sh), resample=self._fast_resample)
    self.mask_tk = ImageTk.PhotoImage(mask_resized)

    # update the existing canvas image item
    self.canvas.itemconfig(self.mask_id, image=self.mask_tk)
    self.canvas.coords(self.mask_id, self.pan_x, self.pan_y)

