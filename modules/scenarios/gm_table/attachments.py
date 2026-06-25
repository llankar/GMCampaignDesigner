"""Attachment discovery helpers for GM Table entity panels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import (
    parse_portrait_value,
    resolve_portrait_candidate,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
MEDIA_FIELDS = ("Portrait", "portrait", "Image", "image")
ATTACHMENT_FIELDS = ("Attachment", "Attachments", "attachment", "attachments")


@dataclass(frozen=True, slots=True)
class EntityAttachment:
    """One displayable or downloadable entity attachment."""

    field_name: str
    path: str
    resolved_path: str | None
    label: str
    is_image: bool


def _split_attachment_value(value) -> list[str]:
    """Parse attachment values saved as lists, literals, lines, or delimited text."""
    paths = parse_portrait_value(value)
    if len(paths) == 1:
        text = paths[0]
        for delimiter in (",",):
            if delimiter in text:
                parts = [part.strip() for part in text.split(delimiter) if part.strip()]
                if parts:
                    return parts
    return paths


def _candidate_values(record: dict) -> Iterable[tuple[str, str]]:
    """Yield raw candidate paths from known media and attachment fields."""
    if not isinstance(record, dict):
        return
    for field_name in (*MEDIA_FIELDS, *ATTACHMENT_FIELDS):
        value = record.get(field_name)
        parser = (
            parse_portrait_value
            if field_name in MEDIA_FIELDS
            else _split_attachment_value
        )
        for path in parser(value):
            cleaned = str(path or "").strip()
            if cleaned:
                yield field_name, cleaned


def _attachment_label(path: str, resolved_path: str | None) -> str:
    """Return a compact label for an attachment path."""
    source = resolved_path or path
    name = Path(source).name
    return name or str(path)


def collect_entity_attachments(
    record: dict, *, campaign_dir: str | None = None
) -> list[EntityAttachment]:
    """Collect de-duplicated media/attachment paths from an entity record."""
    base_dir = campaign_dir or ConfigHelper.get_campaign_dir()
    attachments: list[EntityAttachment] = []
    seen: set[str] = set()
    for field_name, path in _candidate_values(record):
        resolved = resolve_portrait_candidate(path, base_dir)
        key = str(Path(resolved or path)).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        suffix = Path(resolved or path).suffix.casefold()
        attachments.append(
            EntityAttachment(
                field_name=field_name,
                path=path,
                resolved_path=resolved,
                label=_attachment_label(path, resolved),
                is_image=suffix in IMAGE_EXTENSIONS,
            )
        )
    return attachments


def entity_has_attachments(record: dict, *, campaign_dir: str | None = None) -> bool:
    """Return whether an entity has at least one linked attachment/media path."""
    return bool(collect_entity_attachments(record, campaign_dir=campaign_dir))
