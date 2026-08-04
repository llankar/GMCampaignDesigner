"""Pure layout calculations for the Scenario Board scene grid."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneGridCell:
    """Grid coordinates occupied by one scene card."""

    row: int
    column: int
    columnspan: int


def build_scene_grid_layout(
    scene_count: int,
    *,
    columns: int = 20,
    cards_per_row: int = 4,
) -> tuple[SceneGridCell, ...]:
    """Distribute scene cards, letting an incomplete row fill all columns."""
    if scene_count <= 0:
        return ()
    if columns <= 0 or cards_per_row <= 0:
        raise ValueError("columns and cards_per_row must be positive")

    cells: list[SceneGridCell] = []
    for row_start in range(0, scene_count, cards_per_row):
        row_count = min(cards_per_row, scene_count - row_start)
        base_span, extra_columns = divmod(columns, row_count)
        column = 0
        for position in range(row_count):
            span = base_span + (1 if position < extra_columns else 0)
            cells.append(
                SceneGridCell(
                    row=row_start // cards_per_row,
                    column=column,
                    columnspan=span,
                )
            )
            column += span
    return tuple(cells)


def initial_scene_wraplength(columnspan: int, *, column_width: int = 45) -> int:
    """Return a stable first-pass wrap length until Tk reports the card width."""
    return max(120, columnspan * column_width - 14)
