from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.text_helpers import format_multiline_text, deserialize_possible_json
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

ENTITY_WRAPPER_MAP = {
    "places": "places",
    "npcs": "npcs",
    "creatures": "creatures",
    "factions": "factions",
    "objects": "objects",
    "books": "books",
    "maps": "maps",
    "pcs": "pcs",
}

SCENE_RELATED_FIELDS = (
    "NPCs",
    "Creatures",
    "Places",
    "Maps",
    "Objects",
)

SCENARIO_ENTITY_FIELDS = (
    "Places",
    "NPCs",
    "Creatures",
    "Factions",
    "Objects",
    "Books",
)

SCENARIO_ENTITY_FIELD_MAP = {name.lower(): name for name in SCENARIO_ENTITY_FIELDS}


def _decode_longtext_payload(raw_value):
    """Return a structured value for longtext JSON blobs stored as strings."""
    if not isinstance(raw_value, str):
        return raw_value
    stripped = raw_value.strip()
    if not stripped:
        return raw_value
    if not stripped.startswith("{") and not stripped.startswith("["):
        return raw_value
    decoded = deserialize_possible_json(stripped)
    if isinstance(decoded, dict) and ("text" in decoded or "formatting" in decoded):
        return decoded
    return decoded


def _normalise_scene_entries(raw_scenes):
    """Return a list of scene dictionaries from stored payloads."""
    if raw_scenes is None:
        return []
    if isinstance(raw_scenes, str):
        decoded = deserialize_possible_json(raw_scenes)
        if isinstance(decoded, dict) and isinstance(decoded.get("Scenes"), list):
            return decoded.get("Scenes")
        if isinstance(decoded, list):
            return decoded
        return [raw_scenes]
    if isinstance(raw_scenes, dict):
        if isinstance(raw_scenes.get("Scenes"), list):
            return raw_scenes.get("Scenes")
        return [raw_scenes]
    if isinstance(raw_scenes, (list, tuple, set)):
        return list(raw_scenes)
    return [raw_scenes]


def _coerce_name_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or "")
    if not text.strip():
        return []
    parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    return parts or [text.strip()]


def _coerce_scene_text(value):
    value = _decode_longtext_payload(value)
    if isinstance(value, list):
        rendered_parts = []
        for part in value:
            part = _decode_longtext_payload(part)
            if isinstance(part, dict):
                rendered_parts.append(format_multiline_text(part))
            elif part:
                rendered_parts.append(str(part))
        return "\n".join(rendered_parts)
    if isinstance(value, dict):
        return format_multiline_text(value)
    return format_multiline_text(value) if value else ""


def _extract_display_name(value):
    if isinstance(value, dict):
        for key in ("Name", "Title"):
            if value.get(key):
                return str(value.get(key)).strip()
    return str(value).strip()


def _get_entity_wrapper(entity_label):
    slug = ENTITY_WRAPPER_MAP.get(entity_label.lower())
    if not slug:
        return None
    return GenericModelWrapper(slug)


def _build_entity_summary(entity_label, name):
    wrapper = _get_entity_wrapper(entity_label)
    display_name = _extract_display_name(name)
    if not wrapper or not display_name:
        return {"Name": display_name} if display_name else None
    resolved = wrapper.load_item_by_key(display_name)
    if not resolved:
        return {"Name": display_name}
    resolved_name = resolved.get("Name") or resolved.get("Title") or display_name
    summary_text = ""
    for key in ("Description", "Summary", "Notes", "Gist"):
        if resolved.get(key):
            summary_text = _coerce_scene_text(resolved.get(key))
            if summary_text:
                break
    payload = {"Name": str(resolved_name).strip()}
    if summary_text:
        payload["Description"] = summary_text
    return payload


def _resolve_entity_summaries(entity_label, raw_names):
    names = _coerce_name_list(raw_names)
    summaries = []
    for name in names:
        summary = _build_entity_summary(entity_label, name)
        if summary:
            summaries.append(summary)
    return summaries


def _normalise_sections(sections):
    if sections is None:
        return []
    if isinstance(sections, dict):
        return [(str(key), value) for key, value in sections.items()]
    if isinstance(sections, (list, tuple, set)):
        return [(str(section), None) for section in sections]
    return [(str(sections), None)]


def _render_summary_section(scenario):
    summary = _coerce_scene_text(scenario.get("Summary"))
    if not summary:
        return []
    return [{"Text": summary}]


def _render_scene_section(scenario):
    scenes = _normalise_scene_entries(scenario.get("Scenes"))
    if not scenes:
        return []
    payload = []
    for idx, raw_scene in enumerate(scenes, start=1):
        scene = raw_scene if isinstance(raw_scene, dict) else {"Text": raw_scene}
        title = ""
        for key in ("Title", "Scene", "Name", "Heading"):
            if scene.get(key):
                title = str(scene.get(key)).strip()
                if title:
                    break
        if not title:
            title = f"Scene {idx}"

        body_text = ""
        for key in ("Text", "Summary", "Description", "Body", "Notes", "Gist"):
            if scene.get(key):
                body_text = _coerce_scene_text(scene.get(key))
                if body_text:
                    break

        related_payload = {}
        for label in SCENE_RELATED_FIELDS:
            names = _coerce_name_list(scene.get(label) or scene.get(label.lower()))
            if names:
                related_payload[label] = _resolve_entity_summaries(label, names)

        entry = {"Title": title}
        if body_text:
            entry["Text"] = body_text
        if related_payload:
            entry["Related"] = related_payload
        payload.append(entry)
    return payload


def _render_entity_section(scenario, section_name):
    names = _coerce_name_list(scenario.get(section_name) or scenario.get(section_name.lower()))
    if not names:
        return []
    return _resolve_entity_summaries(section_name, names)


def _render_generic_text_section(scenario, section_name):
    value = scenario.get(section_name)
    if value is None:
        return []
    text = _coerce_scene_text(value)
    if not text:
        return []
    return [{"Text": text}]


def build_newsletter_payload(scenario_title, sections, language, style):
    """Build a neutral newsletter payload from a scenario.

    Returns a dict mapping section names to lists of items.
    """
    scenario_wrapper = GenericModelWrapper("scenarios")
    scenario = scenario_wrapper.load_item_by_key(scenario_title, key_field="Title")
    if not scenario:
        return {}

    section_specs = _normalise_sections(sections)
    if not section_specs:
        section_specs = [
            ("Summary", None),
            ("Scenes", None),
            *[(name, None) for name in SCENARIO_ENTITY_FIELDS],
        ]

    payload = {}
    for section_name, _config in section_specs:
        section_key = str(section_name or "").strip()
        if not section_key:
            continue
        section_lower = section_key.lower()
        if section_lower == "secrets":
            continue
        if section_lower == "summary":
            items = _render_summary_section(scenario)
        elif section_lower == "scenes":
            items = _render_scene_section(scenario)
        elif section_lower in SCENARIO_ENTITY_FIELD_MAP:
            canonical_name = SCENARIO_ENTITY_FIELD_MAP[section_lower]
            items = _render_entity_section(scenario, canonical_name)
        else:
            items = _render_generic_text_section(scenario, section_key)
        if items:
            payload[section_key] = items

    return payload
