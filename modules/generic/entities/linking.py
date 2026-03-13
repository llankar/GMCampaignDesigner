from __future__ import annotations

from modules.helpers.template_loader import load_entity_definitions


def _tokenize(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _singularize(label: str) -> str:
    text = str(label or "").strip()
    if text.endswith("ies") and len(text) > 3:
        return text[:-3] + "y"
    if text.endswith("ses") and len(text) > 3:
        return text[:-2]
    if text.endswith("s") and len(text) > 1:
        return text[:-1]
    return text


def entity_label_map() -> dict[str, str]:
    definitions = load_entity_definitions()
    labels: dict[str, str] = {}
    for slug, meta in definitions.items():
        label = str(meta.get("label") or slug.replace("_", " ").title()).strip()
        labels[str(slug)] = label
    return labels


def resolve_entity_slug(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    labels = entity_label_map()
    token = _tokenize(raw)

    for slug, label in labels.items():
        candidates = {
            _tokenize(slug),
            _tokenize(label),
            _tokenize(_singularize(label)),
            _tokenize(slug.rstrip("s")),
        }
        if token in candidates:
            return slug

    fallback = raw.replace(" ", "_").lower()
    if fallback in labels:
        return fallback

    if fallback.endswith("s"):
        singular_fallback = fallback[:-1]
        if singular_fallback in labels:
            return singular_fallback

    return None


def resolve_entity_label(value: str | None) -> str:
    slug = resolve_entity_slug(value)
    if slug:
        return entity_label_map().get(slug, slug.replace("_", " ").title())
    return str(value or "").strip()
