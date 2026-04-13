"""Import helpers for processing AI scenario."""

import json
import re

from modules.scenarios.scene_structured_fields import (
    SCENE_STRUCTURED_SECTION_FIELDS,
    get_structured_field_name_for_section_key,
    normalise_structured_scene_items,
)
from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections

_SCENE_FIELD_MAP = {
    "beats": "SceneBeats",
    "obstacles": "SceneObstacles",
    "clues": "SceneClues",
    "transitions": "SceneTransitions",
    "locations": "SceneLocations",
    "npcs": "SceneNPCs",
}


def parse_json_relaxed(s: str):
    """Try to parse JSON from a possibly noisy AI response (module-level helper)."""
    if not s:
        raise RuntimeError("Empty AI response")
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(json)?", "", s, flags=re.IGNORECASE).strip()
        s = s.rstrip("`").strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start = None
    for i, ch in enumerate(s):
        if ch in "{[":
            start = i
            break
    if start is not None:
        # Handle the branch where start is available.
        tail = s[start:]
        for j in range(len(tail), max(len(tail) - 2000, 0), -1):
            # Process each j from range(len(tail), max(len(tail) - 2000, 0), -1).
            chunk = tail[:j]
            try:
                return json.loads(chunk)
            except Exception:
                continue
    raise RuntimeError("Failed to parse JSON from AI response")


def _clean_code_fence(text: str) -> str:
    """Internal helper for clean code fence."""
    if text and text.strip().startswith("```"):
        return re.sub(r"^```(?:[a-zA-Z]+)?", "", text, flags=re.IGNORECASE).strip().rstrip("`").strip()
    return text


def request_outline(client, compressed_context: str, chunk_range_hint: str, source_label: str, multiple_scenarios: bool):
    """Handle request outline."""
    if multiple_scenarios:
        # Continue with this path when multiple scenarios is set.
        outline_schema = {
            "Scenarios": [
                {
                    "Title": "text",
                    "Summary": "short text (3-5 sentences)",
                    "Scenes": [{"Title": "text", "Gist": "1-3 sentences"}],
                    "NPCs": ["Name"],
                    "Places": ["Name"],
                }
            ]
        }
        prompt_prefix = (
            "You are an assistant that extracts multiple RPG scenario outlines from source text.\n"
            "Detect how many distinct scenarios/adventures are described.\n"
            "Return STRICT JSON only, no prose.\n\n"
        )
    else:
        outline_schema = {
            "Title": "text",
            "Summary": "short text (3-5 sentences)",
            "Scenes": [{"Title": "text", "Gist": "1-3 sentences"}],
            "NPCs": ["Name"],
            "Places": ["Name"],
        }
        prompt_prefix = (
            "You are an assistant that extracts a high-level scenario outline from RPG source text.\n"
            "Return STRICT JSON only, no prose.\n\n"
        )

    prompt_outline = (
        f"{prompt_prefix}"
        f"Source: {source_label}\n"
        "Use the provided chunk summaries (with token ranges) as your evidence.\n"
        "Keep the original language.\n\n"
        "If uncertain, prefer omitting details over inventing them.\n\n"
        f"Chunk map:\n{chunk_range_hint or 'No chunk metadata available.'}\n\n"
        "JSON schema:\n" + json.dumps(outline_schema, ensure_ascii=False, indent=2) + "\n\n"
        "Notes: Use only info from the text. If uncertain, omit.\n"
        "Now outline this text (summaries stitched from the source):\n" + compressed_context
    )
    outline_raw = client.chat(
        [
            {"role": "system", "content": "Extract concise scenario outlines as strict JSON."},
            {"role": "user", "content": prompt_outline},
        ]
    )
    outline = parse_json_relaxed(outline_raw)

    if multiple_scenarios:
        # Continue with this path when multiple scenarios is set.
        scenarios = []
        if isinstance(outline, dict):
            scenarios = outline.get("Scenarios") or []
        elif isinstance(outline, list):
            scenarios = outline
        if not isinstance(scenarios, list):
            raise RuntimeError("AI did not return a JSON list of scenarios")
        return [s for s in scenarios if isinstance(s, dict)]

    if not isinstance(outline, dict):
        raise RuntimeError("AI did not return a JSON object for outline")
    return [outline]


def expand_summary(client, title: str, summary_draft: str, compressed_context: str, chunk_range_hint: str) -> str:
    """Handle expand summary."""
    prompt_summary = (
        "Rewrite the following scenario summary into a richer, evocative, GM-friendly 2–4 paragraph summary.\n"
        "- Keep the original language.\n\n"
        "- Keep it consistent with the source text.\n"
        "- Avoid rules jargon.\n"
        "Return PLAIN TEXT only.\n\n"
        f"Title: {title}\n"
        f"Chunk map for traceability:\n{chunk_range_hint or 'No chunk metadata available.'}\n\n"
        "Current summary (from outline):\n" + (summary_draft or "") + "\n\n"
        "Reference context (stitched summaries):\n" + compressed_context
    )
    summary_expanded = client.chat(
        [
            {"role": "system", "content": "You write compelling GM-facing RPG summaries. Return plain text."},
            {"role": "user", "content": prompt_summary},
        ]
    )
    return _clean_code_fence(summary_expanded or "").strip()


def expand_scenes(client, title: str, outline_scenes, compressed_context: str, chunk_range_hint: str):
    """Handle expand scenes."""
    scenes_schema = {
        "Scenes": [
            {
                "Title": "text",
                "Summary": "optional 1-2 paragraph prose summary",
                "beats": ["key beat"],
                "obstacles": ["conflict or obstacle"],
                "clues": ["clue or hook"],
                "transitions": ["transition to another scene"],
                "locations": ["important location"],
                "NPCs": ["involved NPC name"],
            }
        ]
    }
    prompt_scenes = (
        "Using the outline below and the source text, produce detailed scene writeups.\n"
        "Keep the original language.\n\n"
        "For each scene, return structured keys for beats, obstacles, clues, transitions, locations, and NPCs.\n"
        "Include an optional prose Summary when it helps readability.\n"
        "Return STRICT JSON only with this schema:\n" + json.dumps(scenes_schema, ensure_ascii=False, indent=2) + "\n\n"
        f"Title: {title}\n"
        "Outline scenes:\n" + json.dumps(outline_scenes, ensure_ascii=False, indent=2) + "\n\n"
        f"Chunk map for traceability:\n{chunk_range_hint or 'No chunk metadata available.'}\n\n"
        "Source context (summarized chunks):\n" + compressed_context
    )
    scenes_raw = client.chat(
        [
            {"role": "system", "content": "Expand scene stubs into detailed, game-usable scenes as strict JSON."},
            {"role": "user", "content": prompt_scenes},
        ]
    )
    scenes_obj = parse_json_relaxed(scenes_raw)
    if not isinstance(scenes_obj, dict) or not isinstance(scenes_obj.get("Scenes"), list):
        raise RuntimeError("AI did not return a JSON object with Scenes")
    scenes_expanded_list = []
    for sc in scenes_obj.get("Scenes", []) or []:
        if not isinstance(sc, dict):
            continue
        scenes_expanded_list.append(_normalise_scene_payload(sc))
    return scenes_expanded_list


def _normalise_scene_payload(scene_payload: dict) -> dict:
    """Normalize AI scene payload into canonical structured scene fields."""
    normalized = {
        "Title": str(scene_payload.get("Title") or scene_payload.get("Name") or "").strip(),
        "Summary": str(scene_payload.get("Summary") or scene_payload.get("Prose") or scene_payload.get("ProseSummary") or "").strip(),
    }

    for source_key, target_key in _SCENE_FIELD_MAP.items():
        value = scene_payload.get(source_key)
        if value is None:
            value = scene_payload.get(source_key.capitalize())
        normalized[target_key] = normalise_structured_scene_items(value)

    has_structured_items = any(normalized.get(item["field"]) for item in SCENE_STRUCTURED_SECTION_FIELDS)
    raw_text = scene_payload.get("Text")
    if not has_structured_items and raw_text:
        text = raw_text.get("text", "") if isinstance(raw_text, dict) else str(raw_text)
        parsed = parse_scene_body_sections(text)
        if not normalized.get("Summary"):
            normalized["Summary"] = str(parsed.get("intro_text") or "").strip()
        for section in parsed.get("sections") or []:
            target_key = get_structured_field_name_for_section_key(section.get("key"))
            if target_key and not normalized.get(target_key):
                normalized[target_key] = normalise_structured_scene_items(section.get("items") or [])

    return normalized


def extract_entities(client, compressed_context: str, chunk_range_hint: str, stats_examples: list):
    """Extract entities."""
    entities_schema = {
        "npcs": [
            {
                "Name": "text",
                "Role": "text",
                "Description": "longtext",
                "Secret": "longtext",
                "Factions": ["Name"],
                "Portrait": "text(optional)",
            }
        ],
        "creatures": [
            {
                "Name": "text",
                "Type": "text",
                "Description": "longtext",
                "Weakness": "longtext",
                "Powers": "longtext",
                "Stats": "longtext",
                "Background": "longtext",
            }
        ],
        "places": [{"Name": "text", "Description": "longtext", "Secrets": "longtext(optional)"}],
        "factions": [{"Name": "text", "Description": "longtext(optional)"}],
    }
    prompt_entities = (
        "Extract RPG entities from the text. Output STRICT JSON only, matching the schema below.\n"
        "Keep the original language.\n\n"
        "If stats are present (even from other systems), convert into concise creature 'Stats' similar to examples. Do not invent facts.\n\n"
        "Schema:\n" + json.dumps(entities_schema, ensure_ascii=False, indent=2) + "\n\n"
        "Examples of desired 'Stats' formatting from the active DB:\n" + json.dumps(stats_examples, ensure_ascii=False, indent=2) + "\n\n"
        f"Chunk map for traceability:\n{chunk_range_hint or 'No chunk metadata available.'}\n\n"
        "Text to analyze (summarized chunks):\n" + compressed_context
    )
    entities_raw = client.chat(
        [
            {"role": "system", "content": "Extract structured entities (NPCs, creatures, places, factions) as strict JSON."},
            {"role": "user", "content": prompt_entities},
        ]
    )
    entities = parse_json_relaxed(entities_raw)
    if not isinstance(entities, dict):
        raise RuntimeError("AI did not return a JSON object for entities")
    return entities
