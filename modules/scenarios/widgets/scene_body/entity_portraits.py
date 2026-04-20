"""Avatar loading helpers for scene body entity chips."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import customtkinter as ctk
from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import parse_portrait_value, resolve_portrait_candidate


GROUP_TO_ENTITY_TYPE = {
    "NPCs": "NPCs",
    "Villains": "Villains",
    "Creatures": "Creatures",
    "Places": "Places",
}

_AVATAR_SIZE = (24, 24)


def attach_entity_avatars(group_label: str, entities: Iterable[dict], gm_view_ref):
    """Attach a mini avatar image to each entity payload when possible."""
    if gm_view_ref is None:
        return list(entities or [])

    entity_type = GROUP_TO_ENTITY_TYPE.get(group_label)
    if not entity_type:
        return list(entities or [])

    wrapper = _resolve_wrapper(gm_view_ref, entity_type)
    if wrapper is None:
        return list(entities or [])

    records_by_name = _load_records_by_name(wrapper)
    prepared = []
    for payload in entities or []:
        updated = dict(payload)
        entity_name = str(updated.get("name") or updated.get("line") or "").strip()
        record = records_by_name.get(entity_name)
        updated["avatar"] = _build_avatar(gm_view_ref, entity_type, entity_name, record)
        prepared.append(updated)

    return prepared


def _resolve_wrapper(gm_view_ref, entity_type: str):
    wrappers = getattr(gm_view_ref, "wrappers", None)
    if isinstance(wrappers, dict):
        return wrappers.get(entity_type)
    return None


def _load_records_by_name(wrapper) -> dict:
    try:
        items = wrapper.load_items() if wrapper else []
    except Exception:
        return {}

    records = {}
    for item in items or []:
        name = str(item.get("Name") or item.get("name") or "").strip()
        if name:
            records[name] = item
    return records


def _build_avatar(gm_view_ref, entity_type: str, entity_name: str, record: dict | None):
    if not entity_name or not record:
        return None

    cache = _avatar_cache(gm_view_ref)
    cache_key = (entity_type, entity_name, _AVATAR_SIZE)
    if cache_key in cache:
        return cache[cache_key]

    image_path = _resolve_record_image_path(record)
    if not image_path:
        cache[cache_key] = None
        return None

    try:
        with Image.open(image_path) as image_obj:
            image_obj = image_obj.convert("RGBA")
            image_obj.thumbnail(_AVATAR_SIZE, Image.Resampling.LANCZOS)
            width = max(1, int(image_obj.width))
            height = max(1, int(image_obj.height))
            avatar = ctk.CTkImage(light_image=image_obj.copy(), dark_image=image_obj.copy(), size=(width, height))
    except Exception:
        avatar = None

    cache[cache_key] = avatar
    return avatar


def _avatar_cache(gm_view_ref) -> dict:
    cache = getattr(gm_view_ref, "_scene_entity_avatar_cache", None)
    if isinstance(cache, dict):
        return cache
    cache = {}
    setattr(gm_view_ref, "_scene_entity_avatar_cache", cache)
    return cache


def _resolve_record_image_path(record: dict) -> str | None:
    candidates = []

    portrait_values = parse_portrait_value(record.get("Portrait") or record.get("portrait"))
    candidates.extend(portrait_values)

    for key in ("Image", "image"):
        value = str(record.get(key) or "").strip()
        if value:
            candidates.append(value)

    for candidate in candidates:
        resolved = resolve_portrait_candidate(candidate, ConfigHelper.get_campaign_dir())
        if resolved:
            return str(Path(resolved))

    return None
