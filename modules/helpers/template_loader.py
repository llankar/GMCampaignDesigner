import json
import os
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_debug, log_function, log_info, log_warning
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

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


@log_function
def load_template(entity_name: str) -> dict:
    """Load template and return merged fields (fields + custom_fields if present).

    Built-in fields remain separate inside the file under "fields". User-added
    fields are persisted under "custom_fields" and merged at runtime for UI.
    """
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
    root = os.path.join("modules")
    out = []
    try:
        for name in os.listdir(root):
            tpl = os.path.join(root, name, f"{name}_template.json")
            if os.path.isfile(tpl):
                out.append(name)
    except Exception as exc:
        log_warning(f"Unable to list entities: {exc}",
                    func_name="modules.helpers.template_loader.list_known_entities")
    log_debug(
        f"Discovered {len(out)} entity templates",
        func_name="modules.helpers.template_loader.list_known_entities",
    )
    return sorted(out)
