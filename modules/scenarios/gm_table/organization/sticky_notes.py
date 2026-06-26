"""Pure sticky-note organization helpers."""

from __future__ import annotations


def normalize_tags(value) -> list[str]:
    """Return a stable list of non-empty sticky-note tags."""
    if isinstance(value, str):
        raw = value.replace("#", " ").replace(",", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw:
        tag = str(item).strip()
        key = tag.casefold()
        if tag and key not in seen:
            tags.append(tag)
            seen.add(key)
    return tags


def sticky_note_state(*, title: str = "", body: str = "", color: str = "Yellow", tags=None, vote_marker: str = "", pinned: bool = False) -> dict:
    """Build serializable sticky-note state with backward-compatible text."""
    clean_title = str(title or "").strip()
    clean_body = str(body or "")
    clean_tags = normalize_tags(tags)
    clean_color = str(color or "Yellow").strip() or "Yellow"
    return {
        "title": clean_title,
        "body": clean_body,
        "text": clean_body,
        "color": clean_color,
        "tags": clean_tags,
        "vote_marker": str(vote_marker or "").strip(),
        "pinned": bool(pinned),
    }


def group_sticky_notes(records: list[dict], by: str) -> dict[str, list[dict]]:
    """Group sticky-note records by tag or color."""
    if by not in {"tag", "color"}:
        raise ValueError(f"Unsupported sticky-note grouping: {by}")
    groups: dict[str, list[dict]] = {}
    for record in records:
        definition = record.get("definition")
        if getattr(definition, "kind", None) != "sticky_note":
            continue
        state = getattr(definition, "state", {}) or {}
        keys = normalize_tags(state.get("tags")) if by == "tag" else [str(state.get("color") or "Yellow")]
        if not keys:
            keys = ["Untagged"]
        for key in keys:
            groups.setdefault(key, []).append(record)
    return groups


def cluster_group_geometries(
    groups: dict[str, list[dict]],
    *,
    start_x: float = 0,
    start_y: float = 0,
    gap: int = 28,
    group_gap: int = 96,
    columns: int = 3,
) -> dict[str, dict]:
    """Return panel_id to geometry mappings that cluster each group near itself.

    Group spacing is based on the actual placed panel widths instead of a fixed
    default, which prevents wide sticky notes from overlapping the next group.
    """
    placements: dict[str, dict] = {}
    group_x = float(start_x)
    safe_columns = max(1, int(columns))
    safe_gap = max(0, int(gap))
    safe_group_gap = max(0, int(group_gap))

    for _group_name, records in groups.items():
        group_right = group_x
        column_widths: dict[int, int] = {}
        row_heights: dict[int, int] = {}
        record_geometries: list[tuple[dict, dict, int, int, int, int]] = []
        for index, record in enumerate(records):
            panel = record.get("panel")
            geometry = (
                panel.floating_geometry_snapshot()
                if panel is not None
                else record.get("geometry", {})
            )
            width = int(geometry.get("width", 360))
            height = int(geometry.get("height", 300))
            col = index % safe_columns
            row = index // safe_columns
            column_widths[col] = max(column_widths.get(col, 0), width)
            row_heights[row] = max(row_heights.get(row, 0), height)
            record_geometries.append((record, geometry, width, height, col, row))

        column_offsets: dict[int, float] = {}
        current_x = group_x
        for col in range(safe_columns):
            column_offsets[col] = current_x
            current_x += column_widths.get(col, 0) + safe_gap

        row_offsets: dict[int, float] = {}
        current_y = float(start_y)
        for row in range(max(row_heights, default=-1) + 1):
            row_offsets[row] = current_y
            current_y += row_heights.get(row, 0) + safe_gap

        for record, geometry, width, height, col, row in record_geometries:
            x = column_offsets[col]
            y = row_offsets[row]
            panel_id = record.get("panel_id")
            if panel_id is None:
                continue
            placements[str(panel_id)] = {
                **geometry,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            }
            group_right = max(group_right, x + width)
        group_x = group_right + safe_group_gap
    return placements
