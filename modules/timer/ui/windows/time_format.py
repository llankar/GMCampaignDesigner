"""Utilities for timer time format."""

from __future__ import annotations


def parse_time_to_seconds(text: str, fallback: float = 300.0) -> float:
    """Parse time to seconds."""
    value = (text or "").strip()
    try:
        # Keep time to seconds resilient if this step fails.
        if ":" in value:
            # Handle the branch where ':' is in value.
            parts = [int(part) for part in value.split(":")]
            if len(parts) == 2:
                minutes, seconds = parts
                return max(0.0, float(minutes * 60 + seconds))
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return max(0.0, float(hours * 3600 + minutes * 60 + seconds))
        return max(0.0, float(value))
    except Exception:
        return max(0.0, float(fallback))


def format_seconds(seconds: float) -> str:
    """Format seconds."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"
