"""Map card helpers for Scenario Board panels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import customtkinter as ctk
from PIL import Image, ImageDraw

_THUMBNAIL_SIZE = (176, 104)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_IMAGE_KEYS = ("Image", "image", "Path", "path", "File", "file")
_NAME_KEYS = ("Name", "Title", "Map", "MapName", "name", "title")
_INFO_KEYS = ("Type", "Category", "Tags", "Kind", "Scale", "Grid", "Description")


@dataclass(frozen=True)
class ScenarioBoardMapCard:
    """Display data for one linked map card."""

    name: str
    subtitle: str = ""
    details: str = ""
    image_path: str = ""
    size_label: str = ""


def build_map_cards(
    map_names: Sequence[str], map_wrapper: object | None
) -> tuple[ScenarioBoardMapCard, ...]:
    """Resolve linked map names into thumbnail-card data."""
    records = _load_map_records(map_wrapper)
    lookup = _build_record_lookup(records)
    cards: list[ScenarioBoardMapCard] = []
    seen: set[str] = set()
    for raw_name in map_names:
        name = str(raw_name or "").strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        record = lookup.get(key, {})
        image_path = _first_value(record, _IMAGE_KEYS)
        cards.append(
            ScenarioBoardMapCard(
                name=_first_value(record, _NAME_KEYS) or name,
                subtitle=_first_info(record),
                details=_description_excerpt(record),
                image_path=image_path,
                size_label=_image_size_label(image_path),
            )
        )
    return tuple(cards)


def create_map_thumbnail(
    image_path: str, *, size: tuple[int, int] = _THUMBNAIL_SIZE
) -> ctk.CTkImage:
    """Create a CTk thumbnail for a map image or a styled placeholder."""
    image = _load_image(image_path) or _placeholder_image(size)
    image = _cover_image(image, size)
    return ctk.CTkImage(light_image=image, dark_image=image, size=size)


def _load_map_records(map_wrapper: object | None) -> list[Mapping[str, Any]]:
    load_items = getattr(map_wrapper, "load_items", None)
    if not callable(load_items):
        return []
    try:
        items = load_items()
    except Exception:
        return []
    return (
        [item for item in items if isinstance(item, Mapping)]
        if isinstance(items, list)
        else []
    )


def _build_record_lookup(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    lookup: dict[str, Mapping[str, Any]] = {}
    for record in records:
        for key in _NAME_KEYS:
            alias = str(record.get(key) or "").strip()
            if alias:
                lookup.setdefault(alias.casefold(), record)
    return lookup


def _first_value(record: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


def _first_info(record: Mapping[str, Any]) -> str:
    values = []
    for key in _INFO_KEYS[:-1]:
        value = str(record.get(key) or "").strip()
        if value:
            values.append(value)
    return " • ".join(values[:2])


def _description_excerpt(record: Mapping[str, Any], *, limit: int = 92) -> str:
    text = str(record.get("Description") or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _image_size_label(image_path: str) -> str:
    path = _resolve_image_path(image_path)
    if path is None:
        return "No image"
    try:
        with Image.open(path) as image:
            return f"{image.width} × {image.height}"
    except Exception:
        return "Image unavailable"


def _load_image(image_path: str) -> Image.Image | None:
    path = _resolve_image_path(image_path)
    if path is None:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _resolve_image_path(image_path: str) -> Path | None:
    raw = str(image_path or "").strip()
    if not raw:
        return None
    path = Path(raw)
    candidates = (
        [path] if path.is_absolute() else [_PROJECT_ROOT / path, Path.cwd() / path]
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def _cover_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    image = image.copy()
    image.thumbnail(
        size,
        Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS,
    )
    canvas = Image.new("RGBA", size, (24, 28, 38, 255))
    x = (target_w - image.width) // 2
    y = (target_h - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def _placeholder_image(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, (31, 35, 48, 255))
    draw = ImageDraw.Draw(image)
    w, h = size
    for offset in range(-h, w, 18):
        draw.line((offset, h, offset + h, 0), fill=(47, 54, 74, 255), width=2)
    draw.rectangle((1, 1, w - 2, h - 2), outline=(91, 107, 139, 255), width=2)
    draw.text((w // 2 - 28, h // 2 - 6), "MAP", fill=(178, 190, 214, 255))
    return image
