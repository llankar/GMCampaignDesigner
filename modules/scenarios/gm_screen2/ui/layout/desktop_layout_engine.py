"""Desktop layout engine for GM Screen 2 panel rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PanelGeometry:
    """Resolved geometry metadata for a panel."""

    panel_id: str
    relx: float
    rely: float
    relwidth: float
    relheight: float


class DesktopLayoutEngine:
    """Compute panel geometry using split ratios and visibility state."""

    def compute(self, panel_ids: list[str], split_ratios: list[float], hidden_panels: set[str]) -> list[PanelGeometry]:
        """Resolve a horizontal panel layout from state values."""
        visible_ids = [panel_id for panel_id in panel_ids if panel_id not in hidden_panels]
        if not visible_ids:
            return []

        ratio_count = len(visible_ids)
        if len(split_ratios) < ratio_count:
            split_ratios = split_ratios + [1.0] * (ratio_count - len(split_ratios))

        normalized = split_ratios[:ratio_count]
        total = sum(normalized) or float(ratio_count)
        normalized = [ratio / total for ratio in normalized]

        x = 0.0
        geometry: list[PanelGeometry] = []
        for panel_id, width in zip(visible_ids, normalized):
            geometry.append(
                PanelGeometry(
                    panel_id=panel_id,
                    relx=x,
                    rely=0.0,
                    relwidth=width,
                    relheight=1.0,
                )
            )
            x += width
        return geometry
