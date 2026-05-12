"""Data helpers for campaign."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from modules.campaigns.shared.arc_parser import coerce_arc_list
from modules.campaigns.shared.arc_status import DEFAULT_SCENARIO_STATUS, canonicalize_scenario_status
from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import coerce_text
from modules.campaigns.ui.graphical_display.text_safety import (
    LABEL_DISPLAY_LIMIT,
    LONGFORM_DISPLAY_LIMIT,
    safe_display_list,
    safe_display_text,
)


@dataclass(slots=True)
class ScenarioEntityLink:
    entity_type: str
    name: str


@dataclass(slots=True)
class CampaignGraphScenario:
    title: str
    summary: str
    status: str = DEFAULT_SCENARIO_STATUS
    briefing: str = ""
    objective: str = ""
    hook: str = ""
    stakes: str = ""
    tags: list[str] = field(default_factory=list)
    entity_links: list[ScenarioEntityLink] = field(default_factory=list)
    entity_type_counts: dict[str, int] = field(default_factory=dict)
    linked_entity_count: int = 0
    linked_places_count: int = 0
    linked_factions_count: int = 0
    linked_villains_count: int = 0
    primary_link_type: str = ""
    scene_count: int = 0
    has_secrets: bool = False
    record_exists: bool = False


@dataclass(slots=True)
class CampaignGraphArc:
    name: str
    status: str
    summary: str
    objective: str
    scenarios: list[CampaignGraphScenario] = field(default_factory=list)


@dataclass(slots=True)
class CampaignGraphPayload:
    name: str
    logline: str
    genre: str
    tone: str
    status: str
    setting: str
    main_objective: str
    stakes: str
    themes: str
    linked_scenario_count: int
    arcs: list[CampaignGraphArc] = field(default_factory=list)


def build_campaign_option_index(
    campaign_items: Iterable[dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Build campaign option index."""
    options: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    for campaign in campaign_items:
        # Process each campaign from campaign_items.
        if not isinstance(campaign, dict):
            continue
        name = safe_display_text(campaign.get("Name"), max_chars=LABEL_DISPLAY_LIMIT)
        if not name or name in index:
            continue
        options.append(name)
        index[name] = campaign
    return options, index


def build_campaign_graph_payload(
    campaign_item: dict[str, Any] | None,
    scenario_items: Iterable[dict[str, Any]],
) -> CampaignGraphPayload | None:
    """Build campaign graph payload."""
    if not isinstance(campaign_item, dict):
        return None

    arcs = coerce_arc_list(campaign_item.get("Arcs"))
    linked_scenarios = _coerce_string_list(campaign_item.get("LinkedScenarios"))
    needed_scenario_titles = _collect_campaign_scenario_titles(arcs, linked_scenarios)
    scenario_index = _build_scenario_index(scenario_items, needed_titles=needed_scenario_titles)
    link_fields = iter_scenario_link_fields()
    used_scenarios: set[str] = set()

    rendered_arcs: list[CampaignGraphArc] = []
    for index, arc in enumerate(arcs, start=1):
        arc_name = safe_display_text(arc.get("name"), max_chars=LABEL_DISPLAY_LIMIT) or f"Arc {index}"
        scenario_names = _coerce_string_list(arc.get("scenarios"))
        rendered_scenarios = [_build_scenario_payload(name, scenario_index, link_fields) for name in scenario_names]
        used_scenarios.update(scenario_names)
        rendered_arcs.append(
            CampaignGraphArc(
                name=arc_name,
                status=safe_display_text(arc.get("status"), max_chars=LABEL_DISPLAY_LIMIT) or "Planned",
                summary=safe_display_text(arc.get("summary"), max_chars=LONGFORM_DISPLAY_LIMIT),
                objective=safe_display_text(arc.get("objective"), max_chars=LONGFORM_DISPLAY_LIMIT),
                scenarios=rendered_scenarios,
            )
        )

    loose_threads = [name for name in linked_scenarios if name not in used_scenarios]
    if loose_threads:
        rendered_arcs.append(
            CampaignGraphArc(
                name="Loose Threads",
                status="In Progress" if rendered_arcs else "Planned",
                summary="Linked scenarios that are not yet anchored to a named campaign arc.",
                objective="Assign these scenarios to a narrative arc when the story sharpens.",
                scenarios=[_build_scenario_payload(name, scenario_index, link_fields) for name in loose_threads],
            )
        )

    return CampaignGraphPayload(
        name=safe_display_text(campaign_item.get("Name"), max_chars=LABEL_DISPLAY_LIMIT) or "Unnamed campaign",
        logline=safe_display_text(campaign_item.get("Logline"), max_chars=LONGFORM_DISPLAY_LIMIT),
        genre=safe_display_text(campaign_item.get("Genre"), max_chars=LABEL_DISPLAY_LIMIT),
        tone=safe_display_text(campaign_item.get("Tone"), max_chars=LABEL_DISPLAY_LIMIT),
        status=safe_display_text(campaign_item.get("Status"), max_chars=LABEL_DISPLAY_LIMIT),
        setting=safe_display_text(campaign_item.get("Setting"), max_chars=LONGFORM_DISPLAY_LIMIT),
        main_objective=safe_display_text(campaign_item.get("MainObjective"), max_chars=LONGFORM_DISPLAY_LIMIT),
        stakes=safe_display_text(campaign_item.get("Stakes"), max_chars=LONGFORM_DISPLAY_LIMIT),
        themes=safe_display_text(campaign_item.get("Themes"), max_chars=LONGFORM_DISPLAY_LIMIT),
        linked_scenario_count=len({*linked_scenarios, *used_scenarios}),
        arcs=rendered_arcs,
    )


def _collect_campaign_scenario_titles(arcs: Iterable[dict[str, Any]], linked_scenarios: Iterable[str]) -> set[str]:
    """Return the display-safe scenario titles referenced by campaign links and arcs."""
    titles = set(linked_scenarios)
    for arc in arcs:
        # Process each arc from arcs.
        if not isinstance(arc, dict):
            continue
        titles.update(_coerce_string_list(arc.get("scenarios")))
    return {title for title in titles if title}


def _build_scenario_index(
    scenario_items: Iterable[dict[str, Any]],
    *,
    needed_titles: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a scenario index limited to titles required by the campaign graph."""
    if needed_titles is not None and not needed_titles:
        return {}

    index: dict[str, dict[str, Any]] = {}
    for raw in scenario_items:
        # Process each raw from scenario_items.
        if not isinstance(raw, dict):
            continue
        title = safe_display_text(raw.get("Title"), max_chars=LABEL_DISPLAY_LIMIT)
        if not title or (needed_titles is not None and title not in needed_titles):
            continue
        index[title] = raw
    return index


def _build_scenario_payload(
    title: str,
    scenario_index: dict[str, dict[str, Any]],
    link_fields: list[tuple[str, str]],
) -> CampaignGraphScenario:
    """Build scenario payload."""
    title = safe_display_text(title, max_chars=LABEL_DISPLAY_LIMIT)
    scenario = scenario_index.get(title, {})
    summary = safe_display_text(scenario.get("Summary"), max_chars=LONGFORM_DISPLAY_LIMIT)
    briefing = _pick_first_text(
        scenario,
        "Briefing",
        "ScenarioBriefing",
        "GMBriefing",
        "SessionBriefing",
        "Brief",
    )
    entity_links: list[ScenarioEntityLink] = []

    for entity_type, field_name in link_fields:
        for name in _coerce_string_list(scenario.get(field_name)):
            entity_links.append(ScenarioEntityLink(entity_type=entity_type, name=name))

    entity_counts = Counter(link.entity_type for link in entity_links)
    objective = _pick_first_text(
        scenario,
        "Objective",
        "Objectives",
        "Goal",
        "Goals",
        "CurrentObjective",
        "MainObjective",
        "DesiredOutcome",
    )
    hook = _pick_first_text(
        scenario,
        "Hook",
        "Hooks",
        "PlotHook",
        "PlotHooks",
        "IntroHook",
        "IncitingIncident",
        "SceneSummary",
    ) or _derive_hook(summary, scenario.get("Scenes"))
    stakes = _pick_first_text(
        scenario,
        "Stakes",
        "Consequences",
        "Outcome",
        "FailureState",
        "Threat",
        "Threats",
    ) or _derive_stakes(summary, scenario.get("Secrets"))
    scene_count = _coerce_scene_count(scenario.get("Scenes"))
    has_secrets = bool(safe_display_text(scenario.get("Secrets"), max_chars=1))

    return CampaignGraphScenario(
        title=title or "Untitled scenario",
        summary=summary,
        status=canonicalize_scenario_status(scenario.get("Status")),
        briefing=briefing,
        objective=objective,
        hook=hook,
        stakes=stakes,
        tags=_build_scenario_tags(entity_counts, scene_count, has_secrets),
        entity_links=entity_links,
        entity_type_counts=dict(entity_counts),
        linked_entity_count=len(entity_links),
        linked_places_count=entity_counts.get("Places", 0),
        linked_factions_count=entity_counts.get("Factions", 0),
        linked_villains_count=entity_counts.get("Villains", 0),
        primary_link_type=max(entity_counts, key=entity_counts.get) if entity_counts else "",
        scene_count=scene_count,
        has_secrets=has_secrets,
        record_exists=bool(scenario),
    )


def iter_scenario_link_fields() -> list[tuple[str, str]]:
    """Handle iter scenario link fields."""
    template = load_template("scenarios")
    links: list[tuple[str, str]] = []
    for field in template.get("fields", []):
        # Process each field from template.get('fields', []).
        field_name = coerce_text(field.get("name")).strip()
        linked_type = coerce_text(field.get("linked_type")).strip()
        if not field_name or not linked_type:
            continue
        links.append((linked_type, field_name))
    return links


def _coerce_string_list(value: Any) -> list[str]:
    """Coerce string list into Tk-safe display values."""
    return safe_display_list(value, item_max_chars=LABEL_DISPLAY_LIMIT)


def _pick_first_text(record: dict[str, Any], *keys: str) -> str:
    """Internal helper for pick first text."""
    for key in keys:
        # Process each key from keys.
        value = record.get(key)
        if isinstance(value, list):
            # Handle the branch where isinstance(value, list).
            joined = " • ".join(_coerce_string_list(value)).strip()
            if joined:
                return safe_display_text(joined, max_chars=LONGFORM_DISPLAY_LIMIT)
        text = safe_display_text(value, max_chars=LONGFORM_DISPLAY_LIMIT)
        if text:
            return text
    return ""


def _derive_hook(summary: str, scenes: Any) -> str:
    """Internal helper for derive hook."""
    first_scene = ""
    if isinstance(scenes, list):
        for scene in scenes:
            # Process each scene from scenes.
            if isinstance(scene, dict):
                first_scene = safe_display_text(
                    scene.get("Title") or scene.get("Scene") or scene.get("Summary") or scene.get("Text"),
                    max_chars=LONGFORM_DISPLAY_LIMIT,
                )
            else:
                first_scene = safe_display_text(scene, max_chars=LONGFORM_DISPLAY_LIMIT)
            if first_scene:
                break
    if first_scene:
        return first_scene
    return _first_sentence(summary)


def _derive_stakes(summary: str, secrets: Any) -> str:
    """Internal helper for derive stakes."""
    secret_text = safe_display_text(secrets, max_chars=LONGFORM_DISPLAY_LIMIT)
    if secret_text:
        return _first_sentence(secret_text)
    sentences = [segment.strip() for segment in str(summary or "").replace("\n", " ").split(".") if segment.strip()]
    if len(sentences) >= 2:
        return sentences[1]
    return ""


def _first_sentence(text: str) -> str:
    """Internal helper for first sentence."""
    for separator in (". ", "\n", "! ", "? "):
        if separator in text:
            return text.split(separator, 1)[0].strip().rstrip(".!?")
    return text.strip()


def _coerce_scene_count(value: Any) -> int:
    """Coerce scene count."""
    return len(value) if isinstance(value, list) else 0


def _build_scenario_tags(entity_counts: Counter[str], scene_count: int, has_secrets: bool) -> list[str]:
    """Build scenario tags."""
    tags: list[str] = []
    if scene_count:
        tags.append(f"{scene_count} scene{'s' if scene_count != 1 else ''}")
    if has_secrets:
        tags.append("GM secrets")
    for entity_type, count in entity_counts.most_common(4):
        tags.append(f"{count} {entity_type.lower()}")
    return tags
