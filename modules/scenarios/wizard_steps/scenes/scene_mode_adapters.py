"""Utilities for scenes scene mode adapters."""

import copy

from modules.scenarios.wizard_steps.scenes.scene_entity_fields import (
    SCENE_ENTITY_FIELDS,
    normalise_entity_list,
)

GUIDED_BOUNDARY_FLOW = (
    ("Hook", "Setup"),
    ("Fallout", "Outcome"),
)

LEGACY_GUIDED_FLOW = (
    ("Hook", "Setup"),
    ("Rising action", "Choice"),
    ("Climax", "Combat"),
    ("Fallout", "Outcome"),
)


def _split_to_list(value):
    """Internal helper for split to list."""
    return normalise_entity_list(value)


def normalise_scene_links(scene):
    """Handle normalise scene links."""
    links_data = []
    raw_links = (scene or {}).get("LinkData") or (scene or {}).get("Links")
    if isinstance(raw_links, list):
        for item in raw_links:
            if isinstance(item, dict):
                # Handle the branch where isinstance(item, dict).
                target = str(item.get("target") or item.get("Scene") or item.get("Next") or "").strip()
                if not target:
                    continue
                text = str(item.get("text") or target).strip()
                links_data.append({"target": target, "text": text})
            elif isinstance(item, str) and item.strip():
                links_data.append({"target": item.strip(), "text": item.strip()})
    if not links_data:
        for target in _split_to_list((scene or {}).get("NextScenes")):
            links_data.append({"target": target, "text": target})
    deduped = []
    seen = set()
    for link in links_data:
        # Process each link from links_data.
        key = (link["target"].casefold(), (link.get("text") or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"target": link["target"], "text": link.get("text") or link["target"]})
    return deduped


def canonicalise_scene(scene, *, index=0):
    """Handle canonicalise scene."""
    if not isinstance(scene, dict):
        return {
            "Title": f"Scene {index + 1}",
            "Summary": str(scene or ""),
            "SceneType": "",
            "LinkData": [],
            "NextScenes": [],
            "_canvas": {},
        }
    data = copy.deepcopy(scene)
    summary = str(data.get("Summary") or data.get("Text") or "").strip()
    links = normalise_scene_links(data)
    return {
        "Title": str(data.get("Title") or data.get("Name") or f"Scene {index + 1}").strip(),
        "Summary": summary,
        "SceneType": str(data.get("SceneType") or data.get("Type") or "").strip(),
        "LinkData": links,
        "NextScenes": [link["target"] for link in links],
        "_canvas": copy.deepcopy(data.get("_canvas") or {}),
        **{
            field_name: normalise_entity_list(data.get(field_name))
            for field_name in SCENE_ENTITY_FIELDS
        },
        "_extra_fields": {
            k: copy.deepcopy(v)
            for k, v in data.items()
            if k not in {
                "Title", "Name", "Summary", "Text", "SceneType", "Type", "LinkData", "Links", "NextScenes", "_canvas", *SCENE_ENTITY_FIELDS
            }
        },
    }


def scenes_to_guided_cards(scenes):
    """Handle scenes to guided cards."""
    canonical = [canonicalise_scene(scene, index=i) for i, scene in enumerate(scenes or [])]
    legacy_four_scene_payload = len(canonical) == len(LEGACY_GUIDED_FLOW)
    if not canonical:
        canonical = [{}, {}]
    elif len(canonical) == 1:
        canonical = [canonical[0], {}]

    first_stage, first_type = GUIDED_BOUNDARY_FLOW[0]
    last_stage, last_type = GUIDED_BOUNDARY_FLOW[-1]

    cards = []
    for idx, scene in enumerate(canonical):
        # Process each (idx, scene) from enumerate(canonical).
        is_first = idx == 0
        is_last = idx == len(canonical) - 1
        stage = ""
        default_type = ""
        if is_first:
            # Continue with this path when is first is set.
            stage = first_stage
            default_type = first_type
        elif is_last:
            # Continue with this path when is last is set.
            stage = last_stage
            default_type = last_type
        else:
            if legacy_four_scene_payload and idx < len(LEGACY_GUIDED_FLOW):
                stage, default_type = LEGACY_GUIDED_FLOW[idx]
            else:
                stage = f"Scene {idx + 1}"
                default_type = "Choice"
        cards.append(
            {
                "stage": stage,
                "Title": scene.get("Title") or stage,
                "Summary": scene.get("Summary") or "",
                "SceneType": scene.get("SceneType") or default_type,
                "_canvas": copy.deepcopy(scene.get("_canvas") or {}),
                **{
                    field_name: normalise_entity_list(scene.get(field_name))
                    for field_name in SCENE_ENTITY_FIELDS
                },
                "_extra_fields": copy.deepcopy(scene.get("_extra_fields") or {}),
            }
        )
    return cards


def guided_cards_to_scenes(cards):
    """Handle guided cards to scenes."""
    raw_cards = [card for card in (cards or []) if isinstance(card, dict)]
    if not raw_cards:
        raw_cards = [{}, {}]
    elif len(raw_cards) == 1:
        raw_cards = [raw_cards[0], {}]

    prepared = []
    last_index = len(raw_cards) - 1
    for idx, card in enumerate(raw_cards):
        # Process each (idx, card) from enumerate(raw_cards).
        is_first = idx == 0
        is_last = idx == last_index
        stage = ""
        default_type = ""
        if is_first:
            stage, default_type = GUIDED_BOUNDARY_FLOW[0]
        elif is_last:
            stage, default_type = GUIDED_BOUNDARY_FLOW[-1]
        else:
            stage = str(card.get("stage") or f"Scene {idx + 1}").strip() or f"Scene {idx + 1}"
            default_type = "Choice"

        title = str(card.get("Title") or stage).strip() or stage
        summary = str(card.get("Summary") or "").strip()
        scene = {
            "Title": title,
            "Summary": summary,
            "SceneType": str(card.get("SceneType") or default_type).strip() or default_type,
            "LinkData": [],
            "NextScenes": [],
            "_canvas": copy.deepcopy(card.get("_canvas") or {}),
            **{
                field_name: normalise_entity_list(card.get(field_name))
                for field_name in SCENE_ENTITY_FIELDS
            },
        }
        extras = card.get("_extra_fields")
        if isinstance(extras, dict):
            scene["_extra_fields"] = copy.deepcopy(extras)
        prepared.append(scene)

    for idx in range(len(prepared) - 1):
        target = prepared[idx + 1]["Title"]
        prepared[idx]["LinkData"] = [{"target": target, "text": target}]
        prepared[idx]["NextScenes"] = [target]

    return prepared
