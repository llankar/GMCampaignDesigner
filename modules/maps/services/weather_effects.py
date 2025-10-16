"""Utilities for procedurally generated weather overlay frames."""
from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw

# Default frame count for procedural weather effects.  The specific
# generators may override this to better fit their motion cycle.
_DEFAULT_FRAME_COUNT = 16

def _apply_opacity(base_alpha: int, opacity: float) -> int:
    return max(0, min(255, int(base_alpha * opacity)))


def _particle_seed(seed: int | None, *components: object) -> int:
    if seed is None:
        seed = 0
    mix = hash(components) & 0xFFFFFFFF
    return (int(seed) ^ mix) & 0xFFFFFFFF


def _generate_rain_frames(
    width: int,
    height: int,
    frame_count: int,
    *,
    seed: int | None,
    opacity: float,
) -> Tuple[List[Image.Image], List[int]]:
    frame_count = max(8, frame_count)
    rng = random.Random(_particle_seed(seed, width, height, "rain"))
    drop_count = max(24, min(600, (width * height) // 4500))
    max_length = max(12, int(height * 0.18))
    base_speed = max(40.0, height / 6.0)

    drops: List[Tuple[float, float, float, float]] = []
    for _ in range(drop_count):
        x = rng.uniform(-width * 0.2, width * 1.2)
        y = rng.uniform(-height, height)
        length = rng.uniform(max_length * 0.35, max_length)
        speed = rng.uniform(base_speed * 0.7, base_speed * 1.3)
        drops.append((x, y, length, speed))

    frames: List[Image.Image] = []
    durations = [80] * frame_count
    tint = (170, 200, 255, _apply_opacity(160, opacity))

    for frame_index in range(frame_count):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for drop in drops:
            x, y, length, speed = drop
            progress = (frame_index / frame_count)
            dy = (speed * progress) % (height + length)
            start_y = y + dy - length
            end_y = start_y + length
            start_x = x + length * 0.15
            end_x = start_x + length * 0.35
            if end_y < -length or start_y > height + length:
                continue
            draw.line((start_x, start_y, end_x, end_y), fill=tint, width=2)
        frames.append(img)

    return frames, durations


def _generate_snow_frames(
    width: int,
    height: int,
    frame_count: int,
    *,
    seed: int | None,
    opacity: float,
) -> Tuple[List[Image.Image], List[int]]:
    frame_count = max(12, frame_count)
    rng = random.Random(_particle_seed(seed, width, height, "snow"))
    flake_count = max(18, min(500, (width * height) // 6000))
    max_radius = max(1.5, min(width, height) * 0.02)
    drift_scale = max(8.0, width / 25.0)

    flakes: List[Tuple[float, float, float, float, float]] = []
    for _ in range(flake_count):
        x = rng.uniform(0, width)
        y = rng.uniform(-height, height)
        radius = rng.uniform(max_radius * 0.4, max_radius)
        speed = rng.uniform(15.0, 40.0)
        drift = rng.uniform(-drift_scale, drift_scale)
        flakes.append((x, y, radius, speed, drift))

    frames: List[Image.Image] = []
    durations = [90] * frame_count
    base_alpha = _apply_opacity(200, opacity)

    for frame_index in range(frame_count):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = frame_index / frame_count
        for flake in flakes:
            x, y, radius, speed, drift = flake
            offset_y = (y + speed * progress) % (height + radius * 2) - radius * 2
            offset_x = (x + drift * math.sin(progress * math.pi * 2)) % (width + radius * 2) - radius
            bbox = (
                offset_x - radius,
                offset_y - radius,
                offset_x + radius,
                offset_y + radius,
            )
            draw.ellipse(bbox, fill=(255, 255, 255, base_alpha))
        frames.append(img)

    return frames, durations


def _generate_fog_frames(
    width: int,
    height: int,
    frame_count: int,
    *,
    seed: int | None,
    opacity: float,
) -> Tuple[List[Image.Image], List[int]]:
    frame_count = max(10, frame_count)
    rng = random.Random(_particle_seed(seed, width, height, "fog"))
    puff_count = max(6, min(120, (width * height) // 90000))
    durations = [120] * frame_count

    centers: List[Tuple[float, float, float, float]] = []
    for _ in range(puff_count):
        cx = rng.uniform(-width * 0.2, width * 1.2)
        cy = rng.uniform(-height * 0.2, height * 1.2)
        radius = rng.uniform(min(width, height) * 0.1, max(width, height) * 0.35)
        drift = rng.uniform(-12.0, 12.0)
        centers.append((cx, cy, radius, drift))

    frames: List[Image.Image] = []
    base_alpha = _apply_opacity(110, opacity)

    for frame_index in range(frame_count):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = frame_index / frame_count
        for cx, cy, radius, drift in centers:
            offset_x = cx + math.sin(progress * math.pi * 2) * drift
            offset_y = cy + math.cos(progress * math.pi * 2) * drift * 0.6
            bbox = (
                offset_x - radius,
                offset_y - radius,
                offset_x + radius,
                offset_y + radius,
            )
            gradient = Image.new("L", (max(1, int(radius * 2)), max(1, int(radius * 2))), 0)
            grad_draw = ImageDraw.Draw(gradient)
            grad_draw.ellipse((0, 0, radius * 2, radius * 2), fill=base_alpha)
            gradient_img = Image.new("RGBA", gradient.size, (255, 255, 255, 0))
            gradient_img.putalpha(gradient)
            img.alpha_composite(gradient_img, dest=(int(offset_x - radius), int(offset_y - radius)))
        frames.append(img)

    return frames, durations


_GENERATORS = {
    "rain": _generate_rain_frames,
    "snow": _generate_snow_frames,
    "fog": _generate_fog_frames,
}


def available_weather_effects() -> Sequence[str]:
    """Return the list of supported procedural weather effects."""
    return tuple(sorted(_GENERATORS.keys()))


def generate_weather_frames(
    effect: str,
    width: int,
    height: int,
    *,
    frame_count: int | None = None,
    seed: int | None = None,
    opacity: float = 1.0,
) -> Tuple[List[Image.Image], List[int]]:
    """Generate procedural frames for the requested weather effect."""
    if width <= 0 or height <= 0:
        return [], []
    normalized = (effect or "").strip().lower()
    generator = _GENERATORS.get(normalized)
    if not generator:
        return [], []
    count = int(frame_count) if frame_count else _DEFAULT_FRAME_COUNT
    opacity = max(0.0, min(1.0, float(opacity)))
    frames, durations = generator(width, height, count, seed=seed, opacity=opacity)
    return frames, durations
