"""Color utilities for the fixed GM Table overlay."""

from __future__ import annotations

OVERLAY_OPACITY = 0.80


def blend_hex_color(
    foreground: str, background: str, opacity: float = OVERLAY_OPACITY
) -> str:
    """Blend ``foreground`` over ``background`` using an opacity value from 0 to 1."""
    alpha = max(0.0, min(1.0, float(opacity)))
    fg = _hex_to_rgb(foreground)
    bg = _hex_to_rgb(background)
    blended = tuple(
        round(fg_part * alpha + bg_part * (1.0 - alpha))
        for fg_part, bg_part in zip(fg, bg)
    )
    return "#{:02X}{:02X}{:02X}".format(*blended)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(char * 2 for char in cleaned)
    if len(cleaned) != 6:
        raise ValueError(f"Unsupported hex color: {value!r}")
    return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))
