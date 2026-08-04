"""Media visibility helpers for GM Table entity panels."""

from __future__ import annotations

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import resolve_portrait_path


def has_displayable_entity_image(
    entity: dict, *, campaign_dir: str | None = None
) -> bool:
    """Return whether the entity has a portrait/image that can be displayed."""
    if not isinstance(entity, dict):
        return False

    base_dir = campaign_dir or ConfigHelper.get_campaign_dir()
    return any(
        resolve_portrait_path(entity.get(field_name), base_dir) is not None
        for field_name in ("Portrait", "Image")
    )
