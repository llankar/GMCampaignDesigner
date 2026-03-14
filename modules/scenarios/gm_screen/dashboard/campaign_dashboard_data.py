from __future__ import annotations

from typing import Any

from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import coerce_text


_CAMPAIGN_LABEL_KEY = "Name"


def load_campaign_entities(wrappers: dict[str, Any]) -> list[dict[str, Any]]:
    """Return campaign entities only (never every entity type)."""

    wrapper = _resolve_campaign_wrapper(wrappers or {})
    if wrapper is None:
        return []

    try:
        items = wrapper.load_items()
    except Exception:
        return []

    catalog: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for raw in items:
        item = raw or {}
        name = coerce_text(item.get(_CAMPAIGN_LABEL_KEY)).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        catalog.append({"entity_type": "Campaigns", "name": name, "item": item})
    return catalog


def _resolve_campaign_wrapper(wrappers: dict[str, Any]) -> Any | None:
    """Find campaign wrapper regardless of key casing/pluralization."""

    if not wrappers:
        return None

    direct = wrappers.get("Campaigns")
    if direct is not None:
        return direct

    for key, wrapper in wrappers.items():
        normalized = coerce_text(key).strip().lower()
        if normalized in {"campaign", "campaigns"}:
            return wrapper

    return None


def build_campaign_option_index(campaigns: list[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    options: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    for campaign in campaigns:
        option = campaign["name"]
        options.append(option)
        index[option] = campaign
    return options, index


def extract_campaign_fields(campaign_item: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not campaign_item:
        return []

    template = load_template("campaigns")
    fields: list[dict[str, Any]] = []

    for field in template.get("fields", []):
        field_name = coerce_text(field.get("name")).strip()
        field_type = coerce_text(field.get("type")).strip() or "text"
        if not field_name:
            continue

        if field_name == "LinkedScenarios":
            continue

        value = campaign_item.get(field_name)
        if _is_empty(value):
            continue

        if field_type == "list":
            items = [coerce_text(v).strip() for v in (value or []) if coerce_text(v).strip()]
            if not items:
                continue
            fields.append(
                {
                    "name": field_name,
                    "type": "list",
                    "values": items,
                    "linked_type": field.get("linked_type"),
                }
            )
            continue

        fields.append(
            {
                "name": field_name,
                "type": field_type,
                "value": value if field_name == "Arcs" else coerce_text(value).strip(),
            }
        )

    return fields


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False
