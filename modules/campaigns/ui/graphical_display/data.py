from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from modules.campaigns.shared.arc_parser import coerce_arc_list
from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import coerce_text


@dataclass(slots=True)
class ScenarioEntityLink:
    entity_type: str
    name: str


@dataclass(slots=True)
class CampaignGraphScenario:
    title: str
    summary: str
    entity_links: list[ScenarioEntityLink] = field(default_factory=list)


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


def build_campaign_option_index(campaign_items: Iterable[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    options: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    for campaign in campaign_items:
        if not isinstance(campaign, dict):
            continue
        name = coerce_text(campaign.get("Name")).strip()
        if not name or name in index:
            continue
        options.append(name)
        index[name] = campaign
    return options, index


def build_campaign_graph_payload(campaign_item: dict[str, Any] | None, scenario_items: Iterable[dict[str, Any]]) -> CampaignGraphPayload | None:
    if not isinstance(campaign_item, dict):
        return None

    scenario_index = _build_scenario_index(scenario_items)
    arcs = coerce_arc_list(campaign_item.get("Arcs"))
    linked_scenarios = _coerce_string_list(campaign_item.get("LinkedScenarios"))
    used_scenarios: set[str] = set()

    rendered_arcs: list[CampaignGraphArc] = []
    for index, arc in enumerate(arcs, start=1):
        arc_name = coerce_text(arc.get("name")).strip() or f"Arc {index}"
        scenario_names = _coerce_string_list(arc.get("scenarios"))
        rendered_scenarios = [_build_scenario_payload(name, scenario_index) for name in scenario_names]
        used_scenarios.update(scenario_names)
        rendered_arcs.append(
            CampaignGraphArc(
                name=arc_name,
                status=coerce_text(arc.get("status")).strip() or "Planned",
                summary=coerce_text(arc.get("summary")).strip(),
                objective=coerce_text(arc.get("objective")).strip(),
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
                scenarios=[_build_scenario_payload(name, scenario_index) for name in loose_threads],
            )
        )

    return CampaignGraphPayload(
        name=coerce_text(campaign_item.get("Name")).strip() or "Unnamed campaign",
        logline=coerce_text(campaign_item.get("Logline")).strip(),
        genre=coerce_text(campaign_item.get("Genre")).strip(),
        tone=coerce_text(campaign_item.get("Tone")).strip(),
        status=coerce_text(campaign_item.get("Status")).strip(),
        setting=coerce_text(campaign_item.get("Setting")).strip(),
        main_objective=coerce_text(campaign_item.get("MainObjective")).strip(),
        stakes=coerce_text(campaign_item.get("Stakes")).strip(),
        themes=coerce_text(campaign_item.get("Themes")).strip(),
        linked_scenario_count=len({*linked_scenarios, *used_scenarios}),
        arcs=rendered_arcs,
    )


def _build_scenario_index(scenario_items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for raw in scenario_items:
        if not isinstance(raw, dict):
            continue
        title = coerce_text(raw.get("Title")).strip()
        if not title:
            continue
        index[title] = raw
    return index


def _build_scenario_payload(title: str, scenario_index: dict[str, dict[str, Any]]) -> CampaignGraphScenario:
    title = coerce_text(title).strip()
    scenario = scenario_index.get(title, {})
    summary = coerce_text(scenario.get("Summary")).strip()
    entity_links: list[ScenarioEntityLink] = []

    for entity_type, field_name in iter_scenario_link_fields():
        for name in _coerce_string_list(scenario.get(field_name)):
            entity_links.append(ScenarioEntityLink(entity_type=entity_type, name=name))

    return CampaignGraphScenario(
        title=title or "Untitled scenario",
        summary=summary,
        entity_links=entity_links,
    )


def iter_scenario_link_fields() -> list[tuple[str, str]]:
    template = load_template("scenarios")
    links: list[tuple[str, str]] = []
    for field in template.get("fields", []):
        field_name = coerce_text(field.get("name")).strip()
        linked_type = coerce_text(field.get("linked_type")).strip()
        if not field_name or not linked_type:
            continue
        links.append((linked_type, field_name))
    return links


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        text = coerce_text(entry).strip()
        if text and text not in result:
            result.append(text)
    return result
