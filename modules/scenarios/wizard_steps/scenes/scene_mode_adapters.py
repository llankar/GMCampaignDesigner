import copy

GUIDED_FLOW = (
    ("Hook", "Setup"),
    ("Rising action", "Choice"),
    ("Climax", "Combat"),
    ("Fallout", "Outcome"),
)


def _split_to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace(";", ",").split(",")]
        return [part for part in parts if part]
    return [str(value).strip()]


def normalise_scene_links(scene):
    links_data = []
    raw_links = (scene or {}).get("LinkData") or (scene or {}).get("Links")
    if isinstance(raw_links, list):
        for item in raw_links:
            if isinstance(item, dict):
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
        key = (link["target"].casefold(), (link.get("text") or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"target": link["target"], "text": link.get("text") or link["target"]})
    return deduped


def canonicalise_scene(scene, *, index=0):
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
        "_extra_fields": {
            k: copy.deepcopy(v)
            for k, v in data.items()
            if k not in {
                "Title", "Name", "Summary", "Text", "SceneType", "Type", "LinkData", "Links", "NextScenes", "_canvas"
            }
        },
    }


def scenes_to_guided_cards(scenes):
    canonical = [canonicalise_scene(scene, index=i) for i, scene in enumerate(scenes or [])]
    cards = []
    for idx, (stage, default_type) in enumerate(GUIDED_FLOW):
        scene = canonical[idx] if idx < len(canonical) else {}
        cards.append(
            {
                "stage": stage,
                "Title": scene.get("Title") or stage,
                "Summary": scene.get("Summary") or "",
                "SceneType": scene.get("SceneType") or default_type,
                "_canvas": copy.deepcopy(scene.get("_canvas") or {}),
                "_extra_fields": copy.deepcopy(scene.get("_extra_fields") or {}),
            }
        )
    return cards


def guided_cards_to_scenes(cards):
    prepared = []
    for idx, (stage, default_type) in enumerate(GUIDED_FLOW):
        card = cards[idx] if idx < len(cards) else {}
        title = str(card.get("Title") or stage).strip() or stage
        summary = str(card.get("Summary") or "").strip()
        scene = {
            "Title": title,
            "Summary": summary,
            "SceneType": str(card.get("SceneType") or default_type).strip() or default_type,
            "LinkData": [],
            "NextScenes": [],
            "_canvas": copy.deepcopy(card.get("_canvas") or {}),
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
