from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(slots=True)
class EdgeDrawSpec:
    edge_id: str
    source_center: tuple[float, float]
    target_center: tuple[float, float]
    selected: bool = False


class EdgeRenderer:
    """Draws and hit-tests edges on a Tk canvas."""

    def __init__(self) -> None:
        self._edge_items: dict[str, int] = {}
        self._edge_specs: dict[str, EdgeDrawSpec] = {}

    def draw_or_update(self, canvas, spec: EdgeDrawSpec) -> int:
        self._edge_specs[spec.edge_id] = spec
        points = self._bezier_points(spec.source_center, spec.target_center)
        color = "#facc15" if spec.selected else "#7dd3fc"
        width = 3 if spec.selected else 2

        item_id = self._edge_items.get(spec.edge_id)
        if item_id is None:
            item_id = canvas.create_line(*points, smooth=True, splinesteps=20, fill=color, width=width, tags=("edge", spec.edge_id))
            self._edge_items[spec.edge_id] = item_id
        else:
            canvas.coords(item_id, *points)
            canvas.itemconfig(item_id, fill=color, width=width)
        return item_id

    def remove(self, canvas, edge_id: str) -> None:
        item_id = self._edge_items.pop(edge_id, None)
        self._edge_specs.pop(edge_id, None)
        if item_id is not None:
            canvas.delete(item_id)

    def clear(self, canvas) -> None:
        for item_id in self._edge_items.values():
            canvas.delete(item_id)
        self._edge_items.clear()
        self._edge_specs.clear()

    def hit_test(self, x: float, y: float, threshold: float = 8.0) -> str | None:
        for edge_id, spec in self._edge_specs.items():
            points = self._bezier_points(spec.source_center, spec.target_center)
            for i in range(0, len(points) - 2, 2):
                if self._distance_to_segment((x, y), (points[i], points[i + 1]), (points[i + 2], points[i + 3])) <= threshold:
                    return edge_id
        return None

    def _bezier_points(self, source: tuple[float, float], target: tuple[float, float]) -> list[float]:
        sx, sy = source
        tx, ty = target
        offset = max(40.0, abs(tx - sx) * 0.4)
        cx1 = sx + offset
        cy1 = sy
        cx2 = tx - offset
        cy2 = ty
        return [sx, sy, cx1, cy1, cx2, cy2, tx, ty]

    @staticmethod
    def _distance_to_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        px, py = p
        ax, ay = a
        bx, by = b
        abx, aby = bx - ax, by - ay
        apx, apy = px - ax, py - ay
        ab_len_sq = abx * abx + aby * aby
        if ab_len_sq == 0:
            return hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))
        closest_x = ax + t * abx
        closest_y = ay + t * aby
        return hypot(px - closest_x, py - closest_y)
