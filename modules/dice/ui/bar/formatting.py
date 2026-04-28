"""Formatting helpers for dice bar output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from modules.dice import dice_engine


@dataclass(frozen=True)
class TextSegment:
    """Represents a portion of result text and its emphasis preference."""

    text: str
    emphasize: bool = False


@dataclass(frozen=True)
class ResultChip:
    """Visual token representing one portion of a dice roll breakdown."""

    title: str
    detail: str
    total: str
    highlight: bool = False


@dataclass(frozen=True)
class FormattedRoll:
    """Container for the textual and visual representation of a roll."""

    segments: List[TextSegment]
    total_text: str
    header: str
    chips: List[ResultChip]


def join_parts(parts: List[List[TextSegment]]) -> List[TextSegment]:
    """Join formatted segments with separators."""
    segments: List[TextSegment] = []
    for index, part in enumerate(parts):
        if index:
            segments.append(TextSegment(" | "))
        segments.extend(part)
    return segments


def format_roll_output(result: dice_engine.RollResult, separate: bool) -> FormattedRoll:
    """Format a roll result for the compact bar UI."""
    canonical = result.canonical()
    modifier = result.modifier
    total = result.total

    header = f"{canonical} →" if canonical else "Last Roll"
    segments: List[TextSegment] = []
    if canonical:
        segments.append(TextSegment(f"{canonical} -> "))

    chips: List[ResultChip] = []

    if separate:
        parts: List[List[TextSegment]] = []
        counters: dict[int, int] = {}
        for chain in result.chains:
            counters[chain.faces] = counters.get(chain.faces, 0) + 1
            label = f"d{chain.faces}"
            if result.parsed.dice.get(chain.faces, 0) > 1:
                label = f"{label}#{counters[chain.faces]}"
            values = ", ".join(chain.display_values)
            prefix = f"{label}:[{values}] " if values else f"{label} "
            parts.append([TextSegment(prefix), TextSegment(str(chain.total), emphasize=True)])
            chips.append(ResultChip(title=label, detail=values or "—", total=str(chain.total), highlight=True))
        if modifier:
            mod_text = f"mod {modifier:+d}"
            parts.append([TextSegment(mod_text)])
            chips.append(ResultChip(title="Modifier", detail="Adjustment", total=f"{modifier:+d}", highlight=False))
        breakdown_segments = join_parts(parts)
        segments.extend(breakdown_segments)
        if not breakdown_segments:
            segments.append(TextSegment("0", emphasize=True))
        if not chips:
            chips.append(ResultChip(title="Result", detail="—", total=str(total), highlight=True))
        return FormattedRoll(segments=segments, total_text=f"{total}", header=header, chips=chips)

    parts = []
    for summary in result.face_summaries:
        values = summary.display_values
        detail = ", ".join(values) if values else "—"
        if values:
            prefix = f"{summary.base_count}d{summary.faces}:[{', '.join(values)}] "
        else:
            prefix = f"{summary.base_count}d{summary.faces} "
        parts.append([TextSegment(prefix), TextSegment(str(summary.total), emphasize=True)])
        chips.append(
            ResultChip(
                title=f"{summary.base_count}d{summary.faces}",
                detail=detail,
                total=str(summary.total),
                highlight=True,
            )
        )
    if modifier:
        mod_text = f"mod {modifier:+d}"
        parts.append([TextSegment(mod_text)])
        chips.append(ResultChip(title="Modifier", detail="Adjustment", total=f"{modifier:+d}", highlight=False))
    breakdown_segments = join_parts(parts)
    segments.extend(breakdown_segments)
    if not breakdown_segments:
        segments.append(TextSegment("0", emphasize=True))
    if not chips:
        chips.append(ResultChip(title="Result", detail="—", total=str(total), highlight=True))
    return FormattedRoll(segments=segments, total_text=f"{total}", header=header, chips=chips)
