"""Utilities for procedurally generated weather overlay frames."""
from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter

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
    drop_count = max(36, min(720, (width * height) // 3200))
    max_length = max(6, int(height * 0.06))
    min_length = max(4, int(max_length * 0.45))
    base_speed = max(55.0, height / 4.5)

    drops: List[Tuple[float, float, float, float, float]] = []
    for _ in range(drop_count):
        x = rng.uniform(0, width)
        y = rng.uniform(-height, height)
        length = rng.uniform(min_length, max_length)
        speed = rng.uniform(base_speed * 0.75, base_speed * 1.25)
        drift = rng.uniform(-length * 0.25, length * 0.25)
        drops.append((x, y, length, speed, drift))

    frames: List[Image.Image] = []
    durations = [80] * frame_count
    tint = (190, 215, 255, _apply_opacity(170, opacity))

    for frame_index in range(frame_count):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for drop in drops:
            x, y, length, speed, drift = drop
            progress = (frame_index / frame_count)
            dy = (speed * progress) % (height + length)
            start_y = y + dy - length
            end_y = start_y + length
            start_x = x + drift * 0.25
            end_x = start_x + drift
            if end_y < -length or start_y > height + length:
                continue
            draw.line((start_x, start_y, end_x, end_y), fill=tint, width=1)
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
    flake_count = max(24, min(650, (width * height) // 5000))
    max_radius = max(2.0, min(width, height) * 0.018)
    drift_scale = max(10.0, width / 22.0)

    flakes: List[Tuple[float, float, float, float, float, float, float]] = []
    for _ in range(flake_count):
        x = rng.uniform(0, width)
        y = rng.uniform(-height, height)
        radius = rng.uniform(max_radius * 0.55, max_radius)
        speed = rng.uniform(18.0, 42.0)
        drift = rng.uniform(-drift_scale, drift_scale)
        spin = rng.uniform(0.4, 1.2)
        phase = rng.uniform(0.0, math.tau)
        flakes.append((x, y, radius, speed, drift, spin, phase))

    frames: List[Image.Image] = []
    durations = [90] * frame_count
    base_alpha = _apply_opacity(200, opacity)

    for frame_index in range(frame_count):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        progress = frame_index / frame_count
        for flake in flakes:
            x, y, radius, speed, drift, spin, phase = flake
            offset_y = (y + speed * progress) % (height + radius * 2) - radius * 2
            offset_x = (x + drift * math.sin(progress * math.pi * 2)) % (width + radius * 2) - radius
            angle = phase + progress * math.tau * spin
            diag = radius * 0.7
            color = (255, 255, 255, base_alpha)
            draw.line((offset_x - radius, offset_y, offset_x + radius, offset_y), fill=color, width=1)
            draw.line((offset_x, offset_y - radius, offset_x, offset_y + radius), fill=color, width=1)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            dx = diag * cos_a
            dy = diag * sin_a
            draw.line((offset_x - dx, offset_y - dy, offset_x + dx, offset_y + dy), fill=color, width=1)
            draw.point((offset_x, offset_y), fill=(255, 255, 255, _apply_opacity(255, opacity)))
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
    puff_count = max(6, min(140, (width * height) // 85000))
    durations = [120] * frame_count

    puffs: List[dict] = []
    for _ in range(puff_count):
        cx = rng.uniform(-width * 0.1, width * 1.1)
        cy = rng.uniform(-height * 0.1, height * 1.1)
        radius = rng.uniform(min(width, height) * 0.1, max(width, height) * 0.32)
        mask_size = max(12, int(radius * 2.4))
        mask = Image.new("L", (mask_size, mask_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        point_count = rng.randint(8, 13)
        points = []
        for i in range(point_count):
            angle = (math.tau * i) / point_count
            distance = radius * rng.uniform(0.6, 1.15)
            px = mask_size / 2 + math.cos(angle) * distance * rng.uniform(0.9, 1.2)
            py = mask_size / 2 + math.sin(angle) * distance * rng.uniform(0.7, 1.3)
            points.append((px, py))
        mask_draw.polygon(points, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius * 0.35))
        puffs.append(
            {
                "cx": cx,
                "cy": cy,
                "mask": mask,
                "phase": rng.uniform(0.0, math.tau),
                "cycle": rng.uniform(0.4, 1.0),
                "drift_x": rng.uniform(-20.0, 20.0),
                "drift_y": rng.uniform(-12.0, 12.0),
                "scale": rng.uniform(0.9, 1.25),
                "scale_variation": rng.uniform(0.05, 0.2),
                "stretch_x": rng.uniform(0.85, 1.25),
                "stretch_y": rng.uniform(0.85, 1.25),
            }
        )

    frames: List[Image.Image] = []
    base_color = (235, 238, 245)
    base_alpha = _apply_opacity(120, opacity)

    for frame_index in range(frame_count):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        progress = frame_index / frame_count
        for puff in puffs:
            wave = progress * puff["cycle"] * math.tau + puff["phase"]
            offset_x = puff["cx"] + math.cos(wave) * puff["drift_x"]
            offset_y = puff["cy"] + math.sin(wave * 0.8) * puff["drift_y"]
            scale_factor = puff["scale"] + math.sin(wave * 0.5) * puff["scale_variation"]
            mask = puff["mask"]
            target_w = max(6, int(mask.width * scale_factor * puff["stretch_x"]))
            target_h = max(6, int(mask.height * scale_factor * puff["stretch_y"]))
            if target_w != mask.width or target_h != mask.height:
                mask_img = mask.resize((target_w, target_h), resample=Image.BILINEAR)
            else:
                mask_img = mask
            alpha_mask = mask_img.point(lambda a: int(a * base_alpha / 255))
            tinted = Image.new("RGBA", mask_img.size, base_color + (0,))
            tinted.putalpha(alpha_mask)
            img.alpha_composite(
                tinted,
                dest=(int(offset_x - mask_img.width / 2), int(offset_y - mask_img.height / 2)),
            )
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
