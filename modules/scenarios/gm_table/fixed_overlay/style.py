"""Color utilities for the fixed GM Table overlay."""

from __future__ import annotations

# Requested visual behavior: visible fixed overlay at 85% opacity, i.e. 15%
# transparency.
OVERLAY_OPACITY = 0.85
OVERLAY_TRANSPARENCY = round(1.0 - OVERLAY_OPACITY, 2)
OVERLAY_OPACITY_OPTIONS = (1.0, 0.9, 0.85, 0.75, 0.6, 0.4, 0.25)


def normalize_overlay_opacity(value: object) -> float:
    """Return the nearest supported visible opacity, defaulting to 85%."""
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        return OVERLAY_OPACITY
    return min(OVERLAY_OPACITY_OPTIONS, key=lambda option: abs(option - opacity))


def opacity_to_label(opacity: float) -> str:
    """Return the UI label for a visible opacity value."""
    return f"{round(normalize_overlay_opacity(opacity) * 100):d}%"


def label_to_opacity(label: str) -> float:
    """Parse an opacity label such as ``85%`` into a supported opacity value."""
    cleaned = str(label or "").strip().rstrip("%")
    try:
        return normalize_overlay_opacity(float(cleaned) / 100.0)
    except (TypeError, ValueError):
        return OVERLAY_OPACITY


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
