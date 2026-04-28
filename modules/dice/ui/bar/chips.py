"""Chip rendering helpers for dice bar."""

from .formatting import ResultChip


def chip_text(chip: ResultChip) -> str:
    """Build one-line label text for a result chip."""
    detail_text = (chip.detail or "—").strip()
    return f"{chip.title.upper()}: {detail_text} = {chip.total}"
