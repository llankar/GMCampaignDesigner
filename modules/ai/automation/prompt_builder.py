import json
from typing import List, Dict

from modules.helpers.template_loader import load_template
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def _format_fields(fields: List[Dict[str, str]]) -> str:
    lines = []
    for field in fields:
        name = field.get("name")
        field_type = field.get("type", "text")
        if not name:
            continue
        lines.append(f"- {name} ({field_type})")
    return "\n".join(lines)


def build_entity_prompt(entity_slug: str, count: int, user_prompt: str) -> str:
    template = load_template(entity_slug)
    fields = template.get("fields", [])
    field_list = _format_fields(fields)
    schema_hint = {
        "Name": "",
        "Description": "",
    }
    schema_json = json.dumps(schema_hint, indent=2, ensure_ascii=False)

    return (
        "You are generating RPG campaign content. "
        "Return ONLY valid JSON.\n"
        f"Entity type: {entity_slug}\n"
        f"Number of items: {count}\n\n"
        "Use the following fields exactly as keys (keep casing):\n"
        f"{field_list}\n\n"
        "Rules:\n"
        "- Output must be a JSON array of objects.\n"
        "- Use lists for fields typed as list.\n"
        "- Use plain strings for text/longtext/file/audio fields.\n"
        "- Fill missing fields with empty strings or empty lists.\n"
        "- Do not wrap the JSON in markdown fences.\n\n"
        f"Example shape (not actual content):\n{schema_json}\n\n"
        f"User prompt: {user_prompt}\n"
    )


def build_linked_entities_prompt(
    entity_slug: str,
    names: List[str],
    user_prompt: str,
    parent_context: str,
) -> str:
    template = load_template(entity_slug)
    fields = template.get("fields", [])
    field_list = _format_fields(fields)
    name_list = ", ".join(names)

    return (
        "You are generating linked RPG campaign entities. "
        "Return ONLY valid JSON.\n"
        f"Entity type: {entity_slug}\n"
        f"Required names: {name_list}\n\n"
        "Use the following fields exactly as keys (keep casing):\n"
        f"{field_list}\n\n"
        "Rules:\n"
        "- Output must be a JSON array of objects.\n"
        "- Each object must include the exact Name/Title from the required list.\n"
        "- Use lists for fields typed as list.\n"
        "- Use plain strings for text/longtext/file/audio fields.\n"
        "- Fill missing fields with empty strings or empty lists.\n"
        "- Do not wrap the JSON in markdown fences.\n\n"
        f"Parent context:\n{parent_context}\n\n"
        f"User prompt: {user_prompt}\n"
    )
