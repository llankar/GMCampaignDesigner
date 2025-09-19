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
        os.makedirs(os.path.dirname(path), exist_ok=True)

    # Render fields (built-in) with one object per line
    base_fields = list(data.get("fields", []))
    fields_item_lines = []
    for item in base_fields:
        line = json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
        fields_item_lines.append("    " + line)

    # Render custom_fields with one object per line
    custom_list = fields or []
    item_lines = []
    for item in custom_list:
        # Compact object: keys on one line, with spaces after colon/commas
        line = json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
        # Indent list items by 4 spaces to match indent=2 in base
        item_lines.append("    " + line)

    # Build final JSON with both arrays in single-line-per-item style
    out = ["{"]
    out.append("  \"fields\": [")
    if fields_item_lines:
        out.append(",\n".join(fields_item_lines))
    out.append("  ],")
    out.append("  \"custom_fields\": [")
    if item_lines:
        out.append(",\n".join(item_lines))
    out.append("  ]")
    out.append("}\n")
    final_text = "\n".join(out)
    with open(path, "w", encoding="utf-8") as f:
        f.write(final_text)
    log_info(
        f"Saved {len(custom_list)} custom fields for '{entity_name}'",
        func_name="modules.helpers.template_loader.save_custom_fields",
    )


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
