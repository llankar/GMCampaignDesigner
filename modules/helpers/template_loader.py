import json
import os
import re
import shutil
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_debug,
    log_function,
    log_info,
    log_warning,
)
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SKELETON_TEMPLATE = os.path.join("modules", "generic", "new_entity_template_skeleton.json")
_CUSTOM_ENTITY_MANIFEST = "custom_entities.json"

_BUILTIN_ENTITY_METADATA = {
    "scenarios": {"label": "Scenarios", "icon": "assets/scenario_icon.png"},
    "pcs": {"label": "PCs", "icon": "assets/pc_icon.png"},
    "npcs": {"label": "NPCs", "icon": "assets/npc_icon.png"},
    "creatures": {"label": "Creatures", "icon": "assets/creature_icon.png"},
    "factions": {"label": "Factions", "icon": "assets/faction_icon.png"},
    "places": {"label": "Places", "icon": "assets/places_icon.png"},
    "objects": {"label": "Objects", "icon": "assets/objects_icon.png"},
    "informations": {"label": "Informations", "icon": "assets/informations_icon.png"},
    "clues": {"label": "Clues", "icon": "assets/clues_icon.png"},
    "maps": {"label": "Maps", "icon": "assets/maps_icon.png"},
    "books": {"label": "Books", "icon": "assets/books_icon.png"},
}

@log_function
def _default_template_path(entity_name: str) -> str:
    return os.path.join("modules", entity_name, f"{entity_name}_template.json")


@log_function
def _campaign_template_path(entity_name: str) -> str:
    camp = ConfigHelper.get_campaign_dir()
    return os.path.join(camp, "templates", f"{entity_name}_template.json")


@log_function
def _template_path(entity_name: str) -> str:
    """Prefer campaign-local template if it exists, else fall back to defaults."""
    camp_path = _campaign_template_path(entity_name)
    return camp_path if os.path.exists(camp_path) else _default_template_path(entity_name)


@log_function
def _load_base_template(entity_name: str) -> dict:
    """Load the current template JSON (campaign-local if present)."""
    with open(_template_path(entity_name), "r", encoding="utf-8") as f:
        return json.load(f)


def _custom_manifest_path() -> str:
    camp = ConfigHelper.get_campaign_dir()
    return os.path.join(camp, "templates", _CUSTOM_ENTITY_MANIFEST)


def _load_custom_manifest() -> dict:
    path = _custom_manifest_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        log_warning(
            f"Unable to read custom entity manifest: {exc}",
            func_name="modules.helpers.template_loader._load_custom_manifest",
        )
        return {}
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        # Legacy list format: convert to dict assuming each entry has slug key
        converted = {}
        for entry in data:
            if isinstance(entry, dict) and entry.get("slug"):
                slug = str(entry["slug"])
                converted[slug] = {
                    key: value for key, value in entry.items() if key != "slug"
                }
        return converted
    return {}


def _save_custom_manifest(manifest: dict):
    path = _custom_manifest_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


def _resolve_icon_path(icon_value: str | None) -> str | None:
    if not icon_value:
        return None
    candidates = []
    if os.path.isabs(icon_value):
        candidates.append(icon_value)
    else:
        candidates.append(os.path.join(_PROJECT_ROOT, icon_value))
        candidates.append(os.path.join(ConfigHelper.get_campaign_dir(), icon_value))
        candidates.append(os.path.join(ConfigHelper.get_campaign_dir(), "assets", icon_value))
        if os.path.sep in icon_value:
            candidates.append(icon_value)
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _prepare_icon_for_entity(entity_slug: str, icon_source: str | None) -> str | None:
    if not icon_source:
        return None
    if not os.path.exists(icon_source):
        log_warning(
            f"Icon source '{icon_source}' does not exist",
            func_name="modules.helpers.template_loader._prepare_icon_for_entity",
        )
        return None
    dest_dir = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "icons")
    os.makedirs(dest_dir, exist_ok=True)
    ext = os.path.splitext(icon_source)[1] or ".png"
    dest_path = os.path.join(dest_dir, f"{entity_slug}{ext.lower()}")
    try:
        shutil.copyfile(icon_source, dest_path)
    except Exception as exc:
        log_warning(
            f"Unable to copy icon '{icon_source}': {exc}",
            func_name="modules.helpers.template_loader._prepare_icon_for_entity",
        )
        return None
    return dest_path


@log_function
def load_entity_definitions() -> dict:
    """Return mapping of entity slug to metadata (label, icon, is_custom)."""
    defs = {}
    for slug, meta in _BUILTIN_ENTITY_METADATA.items():
        defs[slug] = {
            "label": meta.get("label") or slug.replace("_", " ").title(),
            "icon": meta.get("icon"),
            "is_custom": False,
        }

    custom_manifest = _load_custom_manifest()
    for slug, meta in custom_manifest.items():
        label = meta.get("label") or slug.replace("_", " ").title()
        defs[slug] = {
            "label": label,
            "icon": meta.get("icon"),
            "is_custom": True,
        }

    resolved = {}
    for slug, meta in defs.items():
        tpl_path = _template_path(slug)
        if not os.path.exists(tpl_path):
            continue
        resolved[slug] = {
            "label": meta["label"],
            "icon": _resolve_icon_path(meta.get("icon")),
            "is_custom": meta.get("is_custom", False),
        }
    return resolved


@log_function
def load_template(entity_name: str) -> dict:
    """Load template and return merged fields (fields + custom_fields if present).

    Built-in fields remain separate inside the file under "fields". User-added
    fields are persisted under "custom_fields" and merged at runtime for UI.
    """
    if not entity_name:
        raise ValueError("entity_name must be provided to load a template")

    data = _load_base_template(entity_name)
    base_fields = list(data.get("fields", []))
    existing_names = {str(f.get("name", "")).strip() for f in base_fields}
    custom_fields = list(data.get("custom_fields", []))

    merged = list(base_fields)
    for fld in custom_fields:
        try:
            name = str(fld.get("name", "")).strip()
            ftype = str(fld.get("type", "text")).strip() or "text"
            if not name or name in existing_names:
                continue
            out = {"name": name, "type": ftype}
            if ftype in ("list", "list_longtext") and fld.get("linked_type"):
                out["linked_type"] = str(fld.get("linked_type"))
            merged.append(out)
        except Exception as exc:
            log_warning(f"Skipping invalid custom field for {entity_name}: {exc}",
                        func_name="modules.helpers.template_loader.load_template")
            continue
    log_info(
        f"Loaded template '{entity_name}' with {len(merged)} fields",
        func_name="modules.helpers.template_loader.load_template",
    )
    return {"fields": merged}


@log_function
def create_custom_entity(entity_slug: str, display_name: str, icon_source: str | None = None) -> dict:
    """Create a campaign-local template for ``entity_slug`` and register metadata."""

    slug = str(entity_slug or "").strip().lower()
    if not slug or not re.fullmatch(r"[a-z0-9_]+", slug):
        raise ValueError("Entity identifier must contain only lowercase letters, numbers, or underscores")

    manifest = _load_custom_manifest()
    if slug in manifest or slug in _BUILTIN_ENTITY_METADATA:
        raise ValueError(f"Entity '{slug}' already exists")

    template_path = _campaign_template_path(slug)
    if os.path.exists(template_path):
        raise ValueError(f"Template for '{slug}' already exists")

    skeleton_path = os.path.join(_PROJECT_ROOT, _SKELETON_TEMPLATE)
    try:
        with open(skeleton_path, "r", encoding="utf-8") as fh:
            skeleton = json.load(fh)
    except Exception:
        skeleton = {"fields": [{"name": "Name", "type": "text"}], "custom_fields": []}

    fields = list(skeleton.get("fields", []))
    custom_fields = list(skeleton.get("custom_fields", []))
    _write_template_file(template_path, fields, custom_fields)

    icon_path = _prepare_icon_for_entity(slug, icon_source)

    manifest[slug] = {
        "label": display_name,
        "icon": icon_path,
    }
    _save_custom_manifest(manifest)

    try:
        from db.db import ensure_entity_schema

        ensure_entity_schema(slug)
    except Exception as exc:
        log_warning(
            f"Unable to ensure schema for '{slug}': {exc}",
            func_name="modules.helpers.template_loader.create_custom_entity",
        )

    return {
        "slug": slug,
        "label": display_name,
        "icon": icon_path,
        "is_custom": True,
    }


@log_function
def update_custom_entity(
    entity_slug: str,
    display_name: str | None = None,
    *,
    icon_source: str | None = None,
    clear_icon: bool = False,
) -> dict:
    """Update label and/or icon metadata for an existing custom entity."""

    slug = str(entity_slug or "").strip().lower()
    if not slug:
        raise ValueError("Entity identifier is required")
    if slug in _BUILTIN_ENTITY_METADATA:
        raise ValueError("Built-in entities cannot be edited from this dialog")

    manifest = _load_custom_manifest()
    if slug not in manifest:
        raise ValueError(f"Custom entity '{slug}' does not exist")

    entry = manifest[slug]

    if display_name is not None:
        entry["label"] = display_name

    old_icon = entry.get("icon")

    if clear_icon:
        if old_icon and os.path.exists(old_icon):
            try:
                os.remove(old_icon)
            except Exception as exc:
                log_warning(
                    f"Unable to remove icon '{old_icon}': {exc}",
                    func_name="modules.helpers.template_loader.update_custom_entity",
                )
        entry["icon"] = None
    elif icon_source:
        new_icon = _prepare_icon_for_entity(slug, icon_source)
        if new_icon:
            if old_icon and old_icon != new_icon and os.path.exists(old_icon):
                try:
                    os.remove(old_icon)
                except Exception as exc:
                    log_warning(
                        f"Unable to remove icon '{old_icon}': {exc}",
                        func_name="modules.helpers.template_loader.update_custom_entity",
                    )
            entry["icon"] = new_icon

    manifest[slug] = entry
    _save_custom_manifest(manifest)

    return {
        "slug": slug,
        "label": entry.get("label"),
        "icon": entry.get("icon"),
        "is_custom": True,
    }


@log_function
def delete_custom_entity(entity_slug: str):
    """Remove an existing custom entity definition and its template."""

    slug = str(entity_slug or "").strip().lower()
    if not slug:
        raise ValueError("Entity identifier is required")
    if slug in _BUILTIN_ENTITY_METADATA:
        raise ValueError("Built-in entities cannot be removed")

    manifest = _load_custom_manifest()
    if slug not in manifest:
        raise ValueError(f"Custom entity '{slug}' does not exist")

    entry = manifest.pop(slug)
    _save_custom_manifest(manifest)

    icon_path = entry.get("icon")
    if icon_path and os.path.exists(icon_path):
        try:
            os.remove(icon_path)
        except Exception as exc:
            log_warning(
                f"Unable to remove icon '{icon_path}': {exc}",
                func_name="modules.helpers.template_loader.delete_custom_entity",
            )

    template_path = _campaign_template_path(slug)
    if os.path.exists(template_path):
        try:
            os.remove(template_path)
        except Exception as exc:
            log_warning(
                f"Unable to remove template '{template_path}': {exc}",
                func_name="modules.helpers.template_loader.delete_custom_entity",
            )

    conn = None
    try:
        from db.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {slug}")
        conn.commit()
    except Exception as exc:
        log_warning(
            f"Unable to drop table '{slug}': {exc}",
            func_name="modules.helpers.template_loader.delete_custom_entity",
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return {
        "slug": slug,
        "label": entry.get("label"),
        "icon": None,
        "is_custom": True,
    }


def _render_template_content(fields: list, custom_fields: list) -> str:
    """Return the canonical JSON body for a template file."""

    def _render_items(items):
        rendered = []
        for item in items:
            line = json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
            rendered.append("    " + line)
        return rendered

    out = ["{"]
    out.append("  \"fields\": [")
    field_lines = _render_items(fields)
    if field_lines:
        out.append(",\n".join(field_lines))
    out.append("  ],")
    out.append("  \"custom_fields\": [")
    custom_lines = _render_items(custom_fields)
    if custom_lines:
        out.append(",\n".join(custom_lines))
    out.append("  ]")
    out.append("}\n")
    return "\n".join(out)


def _write_template_file(path: str, fields: list, custom_fields: list):
    """Write template content to ``path`` using canonical formatting."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = _render_template_content(fields, custom_fields)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


@log_function
def save_custom_fields(entity_name: str, fields: list):
    """Write custom fields into the entity template file under "custom_fields" key.

    File format goal: keep the overall JSON pretty-printed with indent=2, but
    ensure each custom field object is rendered on a single line for clarity.
    """
    # Always write into the campaign-local template file. If it doesn't exist
    # yet, seed from the default template.
    path = _campaign_template_path(entity_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        with open(_default_template_path(entity_name), "r", encoding="utf-8") as f:
            data = json.load(f)

    base_fields = list(data.get("fields", []))
    custom_list = list(fields or [])
    _write_template_file(path, base_fields, custom_list)
    log_info(
        f"Saved {len(custom_list)} custom fields for '{entity_name}'",
        func_name="modules.helpers.template_loader.save_custom_fields",
    )


@log_function
def sync_campaign_template(entity_name: str) -> bool:
    """Ensure the campaign template for ``entity_name`` matches the default fields.

    Returns ``True`` when the campaign template file was created or updated.
    Existing ``custom_fields`` are preserved when rewriting the file.
    """

    default_path = _default_template_path(entity_name)
    if not os.path.exists(default_path):
        log_warning(
            f"Default template missing for '{entity_name}'",
            func_name="modules.helpers.template_loader.sync_campaign_template",
        )
        return False

    try:
        with open(default_path, "r", encoding="utf-8") as fh:
            default_data = json.load(fh)
    except Exception as exc:
        log_warning(
            f"Unable to load default template for '{entity_name}': {exc}",
            func_name="modules.helpers.template_loader.sync_campaign_template",
        )
        return False

    default_fields = list(default_data.get("fields", []))
    campaign_path = _campaign_template_path(entity_name)
    custom_fields = []
    current_fields = None

    if os.path.exists(campaign_path):
        try:
            with open(campaign_path, "r", encoding="utf-8") as fh:
                campaign_data = json.load(fh)
            custom_fields = list(campaign_data.get("custom_fields", []))
            current_fields = list(campaign_data.get("fields", []))
        except Exception as exc:
            log_warning(
                f"Unable to read campaign template for '{entity_name}': {exc}",
                func_name="modules.helpers.template_loader.sync_campaign_template",
            )
    else:
        custom_fields = list(default_data.get("custom_fields", []))

    if current_fields is not None and current_fields == default_fields:
        return False

    _write_template_file(campaign_path, default_fields, custom_fields)
    log_info(
        f"Synchronized template for '{entity_name}'",
        func_name="modules.helpers.template_loader.sync_campaign_template",
    )
    return True


@log_function
def list_known_entities() -> list:
    entities = sorted(load_entity_definitions().keys())
    log_debug(
        f"Discovered {len(entities)} entity templates",
        func_name="modules.helpers.template_loader.list_known_entities",
    )
    return entities


@log_function
def build_entity_wrappers() -> dict:
    """Return ``slug -> GenericModelWrapper`` for all known entities."""

    from modules.generic.generic_model_wrapper import GenericModelWrapper

    wrappers = {}
    for slug in list_known_entities():
        try:
            wrappers[slug] = GenericModelWrapper(slug)
        except Exception as exc:
            log_warning(
                f"Unable to initialize wrapper for '{slug}': {exc}",
                func_name="modules.helpers.template_loader.build_entity_wrappers",
            )
    return wrappers
