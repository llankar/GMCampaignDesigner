import json

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_function, log_module_import
from modules.importers.pdf_entity_importer import parse_json_relaxed, to_list, to_longtext

log_module_import(__name__)


def normalize_npc_payload(payload):
    """Return the NPC list from various payload shapes."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("npcs", "NPCs"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("Payload must be a list of NPCs or contain an 'npcs' array")


@log_function
def import_npc_records(payload) -> int:
    """Persist a list (or wrapped dict) of NPC entries into the database."""
    npcs = normalize_npc_payload(payload)
    if not npcs:
        raise ValueError("No NPCs found in payload")

    wrapper = GenericModelWrapper("npcs")
    existing = wrapper.load_items()
    new_items = []
    for raw in npcs:
        if not isinstance(raw, dict):
            continue
        item = {
            "Name": raw.get("Name", "Unnamed"),
            "Role": raw.get("Role", ""),
            "Description": to_longtext(raw.get("Description", "")),
            "Secret": to_longtext(raw.get("Secret", raw.get("Secrets", ""))),
            "Quote": raw.get("Quote", ""),
            "RoleplayingCues": to_longtext(raw.get("RoleplayingCues", "")),
            "Personality": to_longtext(raw.get("Personality", "")),
            "Motivation": to_longtext(raw.get("Motivation", "")),
            "Background": to_longtext(raw.get("Background", "")),
            "Traits": to_longtext(raw.get("Traits", "")),
            "Notes": to_longtext(raw.get("Notes", "")),
            "Genre": raw.get("Genre", ""),
            "Factions": to_list(raw.get("Factions", [])),
            "Objects": to_list(raw.get("Objects", [])),
            "Links": raw.get("Links", []) if isinstance(raw.get("Links"), list) else [],
            "Portrait": raw.get("Portrait", ""),
            "Audio": raw.get("Audio", ""),
        }
        new_items.append(item)
    if not new_items:
        raise ValueError("No valid NPC entries were provided")

    wrapper.save_items(existing + new_items)
    return len(new_items)


@log_function
def import_npcs_from_json(raw_text: str) -> int:
    """Parse JSON text containing NPC definitions and import them into the DB."""
    data = parse_json_relaxed(raw_text)
    return import_npc_records(data)


def build_npc_schema() -> dict:
    return {
        "npcs": [
            {
                "Name": "text",
                "Role": "text(optional)",
                "Description": "longtext(optional)",
                "Secret": "longtext(optional)",
                "Quote": "text(optional)",
                "RoleplayingCues": "longtext(optional)",
                "Personality": "longtext(optional)",
                "Motivation": "longtext(optional)",
                "Background": "longtext(optional)",
                "Traits": "longtext(optional)",
                "Notes": "longtext(optional)",
                "Genre": "text(optional)",
                "Factions": "list of faction names(optional)",
                "Objects": "list of object names(optional)",
                "Portrait": "url or file(optional)",
                "Audio": "url or file(optional)",
            }
        ]
    }


def build_npc_prompt(raw_text: str, source_label: str) -> str:
    schema = build_npc_schema()
    return (
        "You are an assistant that extracts NPC profiles from tabletop RPG PDFs.\n"
        "Return STRICT JSON only using the schema below.\n"
        "Do not invent details—leave fields empty if the PDF omits them.\n"
        "Preserve line breaks for longtext fields so they remain readable.\n\n"
        "Schema:\n" + json.dumps(schema, ensure_ascii=False, indent=2) + "\n\n"
        f"Source: {source_label or 'Unknown'}\n"
        "PDF text (may be truncated):\n" + raw_text[:5000000]
    )
