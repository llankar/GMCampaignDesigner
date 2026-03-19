from __future__ import annotations


def minimum_scenarios_per_arc(total_available_scenarios: int | None) -> int:
    """Return the minimum scenarios each generated arc should contain."""

    if total_available_scenarios is None:
        return 3
    return 3 if total_available_scenarios >= 3 else max(1, total_available_scenarios)
