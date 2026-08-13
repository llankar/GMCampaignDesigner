"""Data preparation helpers for GM Table scenario board panels."""

from __future__ import annotations

from dataclasses import dataclass
import ast
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping

from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections

SCENARIO_BOARD_ENTITY_TYPES = (
    "NPCs",
    "PCs",
    "Villains",
    "Creatures",
    "Places",
    "Bases",
    "Factions",
    "Objects",
    "Clues",
    "Informations",
    "Maps",
    "Books",
)

NPC_FIELD_ALIASES = (
    "NPCs",
    "NPC",
    "npcs",
    "npc",
    "SceneNPCs",
    "scene_npcs",
    "InvolvedNPCs",
    "Involved NPCs",
    "Characters",
    "characters",
    "Participants",
    "participants",
    "Allies",
    "allies",
    "CriticalNPCs",
)

ENTITY_BLOB_KEYS = (
    "Entities",
    "entities",
    "EntityRefs",
    "entity_refs",
    "Actors",
    "actors",
)

NPC_ENTITY_TYPE_ALIASES = {
    "npc",
    "npcs",
    "character",
    "characters",
    "ally",
    "allies",
    "participant",
    "participants",
}

NPC_ALIAS_STOPWORDS = {
    "archivist",
    "archiviste",
    "bishop",
    "captain",
    "capitaine",
    "chef",
    "colonel",
    "commander",
    "commandant",
    "commandeur",
    "curator",
    "d",
    "dame",
    "de",
    "detective",
    "des",
    "docteur",
    "dr",
    "du",
    "general",
    "generale",
    "guard",
    "inspecteur",
    "l",
    "la",
    "lady",
    "le",
    "les",
    "lieutenant",
    "lord",
    "madame",
    "major",
    "marechal",
    "marquise",
    "monsieur",
    "mr",
    "mrs",
    "ms",
    "of",
    "professeur",
    "security",
    "seigneur",
    "sergent",
    "sir",
    "sister",
    "soeur",
    "the",
    "un",
    "une",
    "warden",
}

NPC_ROLE_ALIASES_ALLOWED_AS_PRIMARY = {
    "garde",
}


@dataclass(frozen=True)
class ScenarioBoardScene:
    """One scene card prepared for the scenario board."""

    index: int
    title: str
    body: str
    intro_text: str
    sections: tuple[dict[str, Any], ...]
    npcs: tuple[str, ...] = ()
    villains: tuple[str, ...] = ()
    places: tuple[str, ...] = ()
    maps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioBoardData:
    """Normalized scenario board payload consumed by the UI."""

    title: str
    status: str
    summary: str
    secrets: str
    objective: str
    pressure: str
    checkpoint: str
    scenes: tuple[ScenarioBoardScene, ...]
    linked_entities: dict[str, tuple[str, ...]]
    character_graph: dict[str, Any]


def _parse_serialized_payload(value: str) -> Any | None:
    """Decode JSON/Python literal rich-text payloads stored as strings."""
    text = value.strip()
    if not text or text[0] not in "[{":
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, (dict, list, tuple)):
            return parsed
    return None


def _clean_text(value: Any) -> str:
    """Return display-safe plain text for raw and rich-text payloads."""
    if value is None:
        return ""
    if isinstance(value, str):
        parsed = _parse_serialized_payload(value)
        if parsed is not None:
            return _clean_text(parsed)
        return value.strip()
    if isinstance(value, Mapping):
        text_value = value.get("text")
        if text_value is None:
            text_value = value.get("Text")
        if text_value is not None:
            return _clean_text(text_value)
        return ""
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return "\n".join(
            part for entry in value if (part := _clean_text(entry))
        ).strip()
    return str(value).strip()


def _maybe_json_list(value: str) -> list[Any] | None:
    """Return a parsed JSON list when a text field stores list data."""
    text = value.strip()
    if not text or text[0] not in '["':
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if isinstance(parsed, list):
        return parsed
    return None


def normalize_list_field(value: Any) -> tuple[str, ...]:
    """Normalize template list/list_longtext fields to a tuple of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        parsed = _maybe_json_list(value)
        if parsed is not None:
            return normalize_list_field(parsed)
        return tuple(
            part.strip()
            for part in value.replace("\r\n", "\n").split("\n")
            if part.strip()
        )
    if isinstance(value, dict):
        for key in ("Title", "Name", "title", "name", "text", "Text"):
            label = _clean_text(value.get(key))
            if label:
                return (label,)
        return ()
    if isinstance(value, Iterable):
        items: list[str] = []
        for entry in value:
            if isinstance(entry, dict):
                label = ""
                for key in ("Title", "Name", "title", "name", "text", "Text"):
                    label = _clean_text(entry.get(key))
                    if label:
                        break
            else:
                label = _clean_text(entry)
            if label:
                items.append(label)
        return tuple(items)
    text = _clean_text(value)
    return (text,) if text else ()


def _dedupe_names(values: Iterable[str]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = str(value or "").strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return tuple(names)


def _fold_mention_text(value: Any) -> str:
    """Normalize case and accents while keeping mention spans comparable."""
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    folded = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return folded.replace("\u0153", "oe").replace("\u00e6", "ae")


def _name_key(value: Any) -> str:
    return _fold_mention_text(value).strip()


def _is_npc_entity_type(raw_type: Any) -> bool:
    normalized = (
        str(raw_type or "").replace("-", " ").replace("_", " ").strip().casefold()
    )
    return normalized in NPC_ENTITY_TYPE_ALIASES


def _entity_name_from_mapping(value: Mapping[str, Any]) -> str:
    for key in ("Name", "Title", "name", "title", "Label", "label", "text", "Text"):
        label = _clean_text(value.get(key))
        if label:
            return label
    return ""


def _extract_npc_blob_names(
    value: Any,
    *,
    default_untyped_to_npc: bool = False,
) -> tuple[str, ...]:
    if isinstance(value, str):
        parsed = _parse_serialized_payload(value)
        if parsed is None:
            return ()
        value = parsed
    if isinstance(value, Mapping):
        names: list[str] = []
        for alias in NPC_FIELD_ALIASES:
            names.extend(normalize_list_field(value.get(alias)))
        typed_name = _entity_name_from_mapping(value)
        raw_type = (
            value.get("type")
            or value.get("Type")
            or value.get("entity_type")
            or value.get("entityType")
            or value.get("category")
            or value.get("Category")
            or value.get("kind")
            or value.get("Kind")
        )
        if typed_name and (
            _is_npc_entity_type(raw_type)
            or (default_untyped_to_npc and not _clean_text(raw_type))
        ):
            names.append(typed_name)
        return _dedupe_names(names)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        names: list[str] = []
        for entry in value:
            if isinstance(entry, Mapping):
                names.extend(
                    _extract_npc_blob_names(
                        entry,
                        default_untyped_to_npc=default_untyped_to_npc,
                    )
                )
                continue
            label = _clean_text(entry)
            if label:
                names.append(label)
        return _dedupe_names(names)
    return ()


def _npc_names_from_mapping(item: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    for alias in NPC_FIELD_ALIASES:
        names.extend(normalize_list_field(item.get(alias)))
    for key in ENTITY_BLOB_KEYS:
        names.extend(
            _extract_npc_blob_names(
                item.get(key),
                default_untyped_to_npc=key.casefold() == "actors",
            )
        )
    return _dedupe_names(names)


def _section_items(
    sections: tuple[dict[str, Any], ...],
    section_key: str,
) -> tuple[str, ...]:
    names: list[str] = []
    for section in sections:
        if str(section.get("key") or "").strip().casefold() == section_key:
            names.extend(normalize_list_field(section.get("items") or ()))
    return _dedupe_names(names)


def _graph_tag_for_npc(name: str, used_tags: set[str]) -> str:
    """Return a stable, canvas-safe graph tag for an NPC name."""
    slug = "".join(
        character if character.isalnum() else "_"
        for character in _fold_mention_text(name).strip()
    ).strip("_")
    base = f"npc_{slug or 'unnamed'}"
    tag = base
    suffix = 1
    while tag in used_tags:
        suffix += 1
        tag = f"{base}_{suffix}"
    used_tags.add(tag)
    return tag


def _layout_npc_graph_node(index: int) -> tuple[int, int]:
    """Return a compact grid position for generated board graph nodes."""
    columns = 4
    return 160 + (index % columns) * 220, 130 + (index // columns) * 150


def _name_mention_pattern(name: str) -> re.Pattern[str] | None:
    """Return a case-insensitive whole-name matcher for scene prose."""
    tokens = re.findall(r"[^\W_]+", _fold_mention_text(name), re.UNICODE)
    if not tokens:
        return None
    escaped = r"[\W_]+".join(re.escape(token) for token in tokens)
    return re.compile(rf"(?<![^\W_]){escaped}(?![^\W_])", re.UNICODE)


def _spans_overlap(span: tuple[int, int], spans: Iterable[tuple[int, int]]) -> bool:
    start, end = span
    return any(
        start < other_end and other_start < end
        for other_start, other_end in spans
    )


def _first_unambiguous_alias(name: str) -> str:
    """Return a conservative first-name alias candidate for a linked NPC."""
    tokens = re.findall(r"[^\W_]+", _fold_mention_text(name), re.UNICODE)
    if len(tokens) < 2:
        return ""
    primary = tokens[0].strip()
    if _name_key(primary) in NPC_ROLE_ALIASES_ALLOWED_AS_PRIMARY:
        return primary
    for token in tokens:
        alias = token.strip()
        if len(alias) < 3:
            continue
        if _name_key(alias) in NPC_ALIAS_STOPWORDS:
            continue
        return alias
    return ""


def _build_unique_npc_aliases(npc_names: Iterable[str]) -> dict[str, str]:
    """Map unique first-name aliases to their canonical linked NPC name."""
    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()
    for name in npc_names:
        alias = _first_unambiguous_alias(name)
        if not alias:
            continue
        key = _name_key(alias)
        if key in aliases and _name_key(aliases[key]) != _name_key(name):
            ambiguous.add(key)
            continue
        aliases[key] = str(name)
    for key in ambiguous:
        aliases.pop(key, None)
    return aliases


def _scene_text_for_npc_mentions(scene: ScenarioBoardScene) -> str:
    """Collect the scene text surfaces where linked NPCs may be mentioned."""
    section_parts: list[str] = []
    for section in scene.sections:
        section_parts.append(_clean_text(section.get("title")))
        section_parts.append(_clean_text(section.get("raw_text")))
        section_parts.extend(_clean_text(item) for item in section.get("items") or ())
    return "\n".join(
        part
        for part in (
            scene.title,
            scene.body,
            scene.intro_text,
            *section_parts,
        )
        if _clean_text(part)
    )


def _detect_linked_npc_mentions(
    npc_names: Iterable[str],
    text: str,
) -> tuple[str, ...]:
    """Find linked NPCs mentioned in free-form scene text.

    Full scenario NPC names are matched first. First-name aliases are only
    considered when they are unique within the scenario cast.
    """
    names = _dedupe_names(npc_names)
    search_text = _fold_mention_text(text)
    if not names or not search_text.strip():
        return ()

    matched_keys: set[str] = set()
    occupied_spans: list[tuple[int, int]] = []
    for name in sorted(names, key=len, reverse=True):
        pattern = _name_mention_pattern(name)
        if pattern is None:
            continue
        for match in pattern.finditer(search_text):
            span = match.span()
            if _spans_overlap(span, occupied_spans):
                continue
            matched_keys.add(_name_key(name))
            occupied_spans.append(span)

    aliases = _build_unique_npc_aliases(names)
    for alias_key, name in sorted(
        aliases.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if _name_key(name) in matched_keys:
            continue
        pattern = _name_mention_pattern(alias_key)
        if pattern is None:
            continue
        for match in pattern.finditer(search_text):
            span = match.span()
            if _spans_overlap(span, occupied_spans):
                continue
            matched_keys.add(_name_key(name))
            occupied_spans.append(span)
            break

    return tuple(name for name in names if _name_key(name) in matched_keys)


def build_scene_npc_character_graph(
    npcs: Iterable[str],
    scenes: Iterable[ScenarioBoardScene],
) -> dict[str, Any]:
    """Build an inspectable NPC graph from scenario cast and scene co-occurrence."""
    scene_entries = tuple(scenes)
    npc_names = _dedupe_names(
        (
            *npcs,
            *(name for scene in scene_entries for name in scene.npcs),
        )
    )
    if not npc_names:
        return {"nodes": [], "links": [], "shapes": []}

    used_tags: set[str] = set()
    tag_by_name: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    for index, name in enumerate(npc_names):
        x, y = _layout_npc_graph_node(index)
        tag = _graph_tag_for_npc(name, used_tags)
        tag_by_name[_name_key(name)] = tag
        nodes.append(
            {
                "entity_type": "npc",
                "entity_name": name,
                "tag": tag,
                "x": x,
                "y": y,
                "color": "#1D3572",
                "collapsed": True,
            }
        )

    links_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    seen_links: set[tuple[str, str, str]] = set()
    for scene in scene_entries:
        scene_npcs = _dedupe_names(
            (
                *scene.npcs,
                *_detect_linked_npc_mentions(
                    npc_names,
                    _scene_text_for_npc_mentions(scene),
                ),
            )
        )
        if len(scene_npcs) < 2:
            continue
        label = scene.title or f"Scene {scene.index}"
        for left_index, left_name in enumerate(scene_npcs):
            left_tag = tag_by_name.get(_name_key(left_name))
            if not left_tag:
                continue
            for right_name in scene_npcs[left_index + 1 :]:
                right_tag = tag_by_name.get(_name_key(right_name))
                if not right_tag:
                    continue
                first_tag, second_tag = sorted((left_tag, right_tag))
                key = (first_tag, second_tag, label)
                if key in seen_links:
                    continue
                seen_links.add(key)
                _merge_graph_link(
                    links_by_pair,
                    {
                        "node1_tag": left_tag,
                        "node2_tag": right_tag,
                        "text": label,
                        "arrow_mode": "both",
                    },
                )

    links = list(links_by_pair.values())
    if not links:
        return {"nodes": [], "links": [], "shapes": []}

    return {"nodes": nodes, "links": links, "shapes": []}


def _legacy_graph_node_name(node: Mapping[str, Any]) -> str:
    return _clean_text(
        node.get("entity_name")
        or node.get("npc_name")
        or node.get("pc_name")
        or node.get("Name")
        or node.get("name")
    )


def _legacy_graph_node_type(node: Mapping[str, Any]) -> str:
    if node.get("npc_name"):
        return "npc"
    if node.get("pc_name"):
        return "pc"
    return _clean_text(node.get("entity_type") or node.get("type")) or "npc"


def _normalize_graph_entity_type(entity_type: Any) -> str:
    normalized = (
        _clean_text(entity_type)
        .replace("-", "_")
        .replace(" ", "_")
        .strip("_")
        .casefold()
    )
    aliases = {
        "character": "npc",
        "characters": "npc",
        "npc": "npc",
        "npcs": "npc",
        "pc": "pc",
        "pcs": "pc",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized.endswith("s"):
        return normalized[:-1]
    return normalized or "npc"


def _default_graph_tag(entity_type: str, entity_name: str) -> str:
    clean_type = str(entity_type or "npc").strip() or "npc"
    clean_name = str(entity_name or "unnamed").strip() or "unnamed"
    return f"{clean_type}_{clean_name.replace(' ', '_')}"


def _normalize_graph_nodes(
    raw_nodes: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str], dict[tuple[str, str], str]]:
    """Return nodes with renderer-compatible unique tags plus lookup maps."""
    nodes: list[dict[str, Any]] = []
    tag_mapping: dict[str, str] = {}
    tag_by_entity: dict[tuple[str, str], str] = {}
    used_tags: set[str] = set()
    for raw_node in raw_nodes:
        node = dict(raw_node)
        entity_type = _normalize_graph_entity_type(_legacy_graph_node_type(node))
        entity_name = _legacy_graph_node_name(node)
        if entity_name:
            node["entity_type"] = entity_type
            node.setdefault("entity_name", entity_name)
        base = _default_graph_tag(entity_type, entity_name)
        original_tag = _clean_text(node.get("tag")) or base
        tag = original_tag
        suffix = 1
        while tag in used_tags:
            tag = f"{base}_{suffix}"
            suffix += 1
        node["tag"] = tag
        used_tags.add(tag)
        tag_mapping[original_tag] = tag
        if entity_name:
            tag_by_entity[(entity_type, _name_key(entity_name))] = tag
        nodes.append(node)
    return nodes, tag_mapping, tag_by_entity


def _legacy_link_entity_tag(
    link: Mapping[str, Any],
    *,
    index: int,
    tag_by_entity: Mapping[tuple[str, str], str],
) -> str:
    npc_name = _clean_text(link.get(f"npc_name{index}"))
    if npc_name:
        return tag_by_entity.get(("npc", _name_key(npc_name)), "")
    pc_name = _clean_text(link.get(f"pc_name{index}"))
    if pc_name:
        return tag_by_entity.get(("pc", _name_key(pc_name)), "")
    name_key = "source_name" if index == 1 else "target_name"
    type_key = "source_type" if index == 1 else "target_type"
    entity_name = _clean_text(link.get(name_key))
    entity_type = _normalize_graph_entity_type(link.get(type_key))
    if not entity_name or not entity_type:
        return ""
    return tag_by_entity.get((entity_type, _name_key(entity_name)), "")


def _normalize_graph_link_tags(
    link: Mapping[str, Any],
    *,
    tag_mapping: Mapping[str, str],
    tag_by_entity: Mapping[tuple[str, str], str],
) -> tuple[str, str]:
    node1_tag = _clean_text(link.get("node1_tag"))
    node2_tag = _clean_text(link.get("node2_tag"))
    if node1_tag:
        node1_tag = tag_mapping.get(node1_tag, node1_tag)
    else:
        node1_tag = _legacy_link_entity_tag(
            link,
            index=1,
            tag_by_entity=tag_by_entity,
        )
    if node2_tag:
        node2_tag = tag_mapping.get(node2_tag, node2_tag)
    else:
        node2_tag = _legacy_link_entity_tag(
            link,
            index=2,
            tag_by_entity=tag_by_entity,
        )
    return node1_tag, node2_tag


def _link_label_parts(text: str) -> list[str]:
    return [part.strip() for part in text.split(" / ") if part.strip()]


def _reverse_arrow_mode(arrow_mode: str) -> str:
    if arrow_mode == "start":
        return "end"
    if arrow_mode == "end":
        return "start"
    return arrow_mode


def _merge_graph_link(
    links_by_pair: dict[tuple[str, str], dict[str, Any]],
    link: Mapping[str, Any],
) -> None:
    node1_tag = _clean_text(link.get("node1_tag"))
    node2_tag = _clean_text(link.get("node2_tag"))
    if not node1_tag or not node2_tag or node1_tag == node2_tag:
        return
    first_tag, second_tag = sorted((node1_tag, node2_tag))
    pair = (first_tag, second_tag)
    label = _clean_text(link.get("text") or link.get("label"))
    arrow_mode = _clean_text(link.get("arrow_mode")) or "both"
    if pair not in links_by_pair:
        stored_node1, stored_node2 = (
            (first_tag, second_tag)
            if arrow_mode in ("both", "none")
            else (node1_tag, node2_tag)
        )
        links_by_pair[pair] = {
            "node1_tag": stored_node1,
            "node2_tag": stored_node2,
            "text": label,
            "arrow_mode": arrow_mode,
        }
        return
    existing = links_by_pair[pair]
    existing_labels = _link_label_parts(_clean_text(existing.get("text")))
    existing_keys = {label_part.casefold() for label_part in existing_labels}
    if label and label.casefold() not in existing_keys:
        existing_labels.append(label)
        existing["text"] = " / ".join(existing_labels)
    existing_node1 = _clean_text(existing.get("node1_tag"))
    existing_node2 = _clean_text(existing.get("node2_tag"))
    if node1_tag == existing_node2 and node2_tag == existing_node1:
        arrow_mode = _reverse_arrow_mode(arrow_mode)
    if existing.get("arrow_mode") != arrow_mode:
        existing["arrow_mode"] = "both"


def normalize_character_graph(value: Any) -> dict[str, Any]:
    """Return a safe scenario character graph payload for display widgets."""
    if isinstance(value, str):
        value = _parse_serialized_payload(value)
    if not isinstance(value, Mapping):
        return {"nodes": [], "links": [], "shapes": []}

    def mapping_list(key: str) -> list[dict[str, Any]]:
        entries = value.get(key)
        if not isinstance(entries, (list, tuple)):
            return []
        return [dict(entry) for entry in entries if isinstance(entry, Mapping)]

    nodes, tag_mapping, tag_by_entity = _normalize_graph_nodes(mapping_list("nodes"))
    node_tags = {node["tag"] for node in nodes}
    links_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_link in mapping_list("links"):
        node1_tag, node2_tag = _normalize_graph_link_tags(
            raw_link,
            tag_mapping=tag_mapping,
            tag_by_entity=tag_by_entity,
        )
        if node1_tag not in node_tags or node2_tag not in node_tags:
            continue
        link = dict(raw_link)
        link["node1_tag"] = node1_tag
        link["node2_tag"] = node2_tag
        link.setdefault("arrow_mode", "both")
        _merge_graph_link(links_by_pair, link)

    return {
        "nodes": nodes,
        "links": list(links_by_pair.values()),
        "shapes": mapping_list("shapes"),
        **({"tabs": mapping_list("tabs")} if isinstance(value.get("tabs"), list) else {}),
        **(
            {"active_tab_id": value["active_tab_id"]}
            if value.get("active_tab_id")
            else {}
        ),
    }


def split_scene_title(scene_text: str, index: int) -> tuple[str, str]:
    """Split a scene longtext block into a card title and body."""
    text = _clean_text(scene_text)
    if not text:
        return f"Scene {index}", ""
    lines = text.splitlines()
    first_line = lines[0].strip()
    if len(lines) > 1 and 0 < len(first_line) <= 90:
        title = first_line.strip("#*: -") or f"Scene {index}"
        return title, "\n".join(lines[1:]).strip()
    for separator in (" — ", " – ", ": "):
        if separator in first_line:
            title, body = first_line.split(separator, 1)
            if title.strip() and len(title.strip()) <= 90:
                remaining = [body.strip(), *lines[1:]]
                return (
                    title.strip("#*: -"),
                    "\n".join(part for part in remaining if part).strip(),
                )
    return f"Scene {index}", text


SCENE_SOURCE_KEYS = ("Scenes", "Scene Flow", "SceneFlow", "scene_flow", "scenes")


def _coerce_scene_entries(item: Mapping[str, Any]) -> list[Any]:
    """Return scene entries from every supported scenario scene field."""
    for key in SCENE_SOURCE_KEYS:
        if key not in item:
            continue
        value = item.get(key)
        if isinstance(value, dict):
            nested = value.get("scenes") or value.get("Scenes")
            if nested is not None:
                value = nested
            else:
                sortable = []
                for scene_key, scene_value in value.items():
                    if isinstance(scene_value, (dict, list, tuple, str)):
                        sortable.append((str(scene_key), scene_value))
                return [
                    entry for _key, entry in sorted(sortable, key=lambda pair: pair[0])
                ]
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            parsed = _maybe_json_list(value)
            if parsed is not None:
                return list(parsed)
            return list(normalize_list_field(value))
    return []


def _scene_field(entry: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in entry and entry.get(key) not in (None, ""):
            return entry.get(key)
    return None


def _normalize_scene_entry(entry: Any, index: int) -> ScenarioBoardScene | None:
    if isinstance(entry, Mapping):
        title = _clean_text(
            _scene_field(
                entry,
                (
                    "Title",
                    "title",
                    "Name",
                    "name",
                    "Scene",
                    "scene",
                    "Heading",
                    "heading",
                ),
            )
        )
        body_value = _scene_field(
            entry,
            (
                "Description",
                "description",
                "Body",
                "body",
                "Text",
                "text",
                "Summary",
                "summary",
            ),
        )
        body = _clean_text(body_value)
        if not title:
            title, body = split_scene_title(body, index)
        parsed = parse_scene_body_sections(body)
        sections = tuple(parsed.get("sections") or ())
        npcs = _dedupe_names(
            (
                *_npc_names_from_mapping(entry),
                *_section_items(sections, "involved npcs"),
            )
        )
        return ScenarioBoardScene(
            index=index,
            title=title or f"Scene {index}",
            body=body,
            intro_text=_clean_text(parsed.get("intro_text")),
            sections=sections,
            npcs=npcs,
            villains=normalize_list_field(
                _scene_field(
                    entry, ("Villains", "villains", "Antagonists", "antagonists")
                )
            ),
            places=normalize_list_field(
                _scene_field(
                    entry,
                    (
                        "Places",
                        "places",
                        "Locations",
                        "locations",
                        "Setting",
                        "setting",
                    ),
                )
            ),
            maps=normalize_list_field(
                _scene_field(
                    entry, ("Maps", "maps", "Map", "map", "SceneMap", "Scene Map")
                )
            ),
        )

    scene_text = _clean_text(entry)
    if not scene_text:
        return None
    title, body = split_scene_title(scene_text, index)
    parsed = parse_scene_body_sections(body or scene_text)
    sections = tuple(parsed.get("sections") or ())
    return ScenarioBoardScene(
        index=index,
        title=title,
        body=body or scene_text,
        intro_text=_clean_text(parsed.get("intro_text")),
        sections=sections,
        npcs=_section_items(sections, "involved npcs"),
    )


def build_scenario_board_data(
    scenario_item: dict[str, Any] | None,
) -> ScenarioBoardData:
    """Build normalized display data for a scenario board panel."""
    item = scenario_item if isinstance(scenario_item, dict) else {}
    scenes: list[ScenarioBoardScene] = []
    for index, entry in enumerate(_coerce_scene_entries(item), start=1):
        scene = _normalize_scene_entry(entry, index)
        if scene is not None:
            scenes.append(scene)

    linked_entities = {
        entity_type: normalize_list_field(item.get(entity_type))
        for entity_type in SCENARIO_BOARD_ENTITY_TYPES
    }
    linked_npcs = _dedupe_names(
        (
            *linked_entities.get("NPCs", ()),
            *_npc_names_from_mapping(item),
            *(name for scene in scenes for name in scene.npcs),
        )
    )
    if linked_npcs:
        linked_entities["NPCs"] = linked_npcs
    linked_entities = {
        entity_type: values for entity_type, values in linked_entities.items() if values
    }
    character_graph = normalize_character_graph(item.get("ScenarioCharacterGraph"))
    if not character_graph.get("nodes"):
        character_graph = build_scene_npc_character_graph(
            linked_entities.get("NPCs", ()),
            scenes,
        )

    def first_text(*keys: str) -> str:
        for key in keys:
            value = _clean_text(item.get(key))
            if value:
                return value
        return ""

    return ScenarioBoardData(
        title=_clean_text(item.get("Title") or item.get("Name")) or "Untitled Scenario",
        status=_clean_text(item.get("Status")),
        summary=_clean_text(item.get("Summary")),
        secrets=_clean_text(item.get("Secrets")),
        objective=first_text(
            "Objectives", "Objective", "MainObjective", "Goal", "Goals"
        ),
        pressure=first_text("Pressure", "Stakes", "Threat", "Complications"),
        checkpoint=first_text("Checkpoint", "Route", "Progression"),
        scenes=tuple(scenes),
        linked_entities=linked_entities,
        character_graph=character_graph,
    )
