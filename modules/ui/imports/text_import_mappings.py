from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


@dataclass(frozen=True)
class TextImportTarget:
    label: str
    slug: str
    name_field: str
    description_field: str
    notes_field: str


TARGETS = (
    TextImportTarget(
        label="PNJ",
        slug="npcs",
        name_field="Name",
        description_field="Description",
        notes_field="Notes",
    ),
    TextImportTarget(
        label="Lieu",
        slug="places",
        name_field="Name",
        description_field="Description",
        notes_field="Notes",
    ),
    TextImportTarget(
        label="Objet",
        slug="objects",
        name_field="Name",
        description_field="Description",
        notes_field="Secrets",
    ),
    TextImportTarget(
        label="Scénario",
        slug="scenarios",
        name_field="Title",
        description_field="Summary",
        notes_field="Secrets",
    ),
)


def list_target_labels() -> list[str]:
    return [target.label for target in TARGETS]


def target_for_label(label: str) -> TextImportTarget:
    for target in TARGETS:
        if target.label == label:
            return target
    return TARGETS[0]


def extract_default_name(text: str, url: str | None) -> str:
    if text:
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned:
                return cleaned[:120]
    if url:
        return url.strip()[:120]
    return ""


def build_source_metadata(text: str, url: str | None, *, excerpt_length: int = 280) -> dict:
    safe_text = (text or "").strip().replace("\n", " ")
    excerpt = safe_text[:excerpt_length]
    if len(safe_text) > excerpt_length:
        excerpt = f"{excerpt}…"
    return {
        "url": url or "",
        "date": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "excerpt": excerpt,
    }
