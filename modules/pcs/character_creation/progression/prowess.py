"""Helpers for prowess-slot and prowess-point progression."""

from __future__ import annotations

from ..constants import RANK_TABLE

BASE_FEAT_COUNT = 2
BASE_PROWESS_POINTS = 6


def rank_index_from_advancement_total(advancements: int) -> int:
    """Resolve rank index from current total advancements."""

    if advancements < 0:
        return 0

    for idx, (start, end, _rank_name, _skill_cap_points) in enumerate(RANK_TABLE):
        if start <= advancements <= end:
            return max(0, idx - 1)

    return max(0, len(RANK_TABLE) - 2)


def prowess_points_from_advancement_choices(advancement_choices: list[dict]) -> list[int]:
    """Return prowess-point budgets granted by selected advancements in chronological order."""

    budgets: list[int] = []
    for advancement_total, choice in enumerate(advancement_choices, start=1):
        choice_type = (choice or {}).get("type", "").strip()
        if choice_type != "prowess_points":
            continue

        rank_index = rank_index_from_advancement_total(advancement_total)
        budgets.append(1 + rank_index)
    return budgets


def expected_feat_count(advancement_choices: list[dict]) -> int:
    """Base feats + one feat for each prowess advancement selection."""

    return BASE_FEAT_COUNT + len(prowess_points_from_advancement_choices(advancement_choices))

