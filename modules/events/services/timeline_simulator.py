from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any

from db.db import get_campaign_setting, set_campaign_setting
from modules.generic.generic_model_wrapper import GenericModelWrapper


_COMPLETED_EVENT_STATUSES = {"resolved", "completed", "done", "cancelled", "canceled"}


@dataclass
class TimelineChange:
    occurred_on: str
    category: str
    entity_type: str
    entity_name: str
    summary: str
    related_places: list[str]
    related_npcs: list[str]
    related_scenarios: list[str]
    related_maps: list[str]
    related_clues: list[str]


@dataclass
class TimelineSimulationResult:
    start_date: date
    end_date: date
    days_advanced: int
    resolved_events: int
    escalated_factions: int
    escalated_villains: int
    advanced_projects: int
    npc_movements: int
    change_count: int
    gm_summary: str
    changes: list[TimelineChange]


class CampaignTimelineSimulator:
    """Advance campaign time and propagate world-state changes into linked entities."""

    ENTITY_TYPES = (
        "events",
        "factions",
        "villains",
        "npcs",
        "bases",
        "places",
        "scenarios",
        "maps",
        "clues",
        "informations",
    )

    def __init__(self, wrappers: dict[str, Any] | None = None):
        self._wrappers = dict(wrappers or {})

    def advance_days(self, days: int) -> TimelineSimulationResult:
        current = self._get_current_date()
        return self.advance_to(current + timedelta(days=max(0, int(days))))

    @classmethod
    def current_campaign_date(cls) -> date:
        return cls._get_current_date()

    def advance_to(self, target_date: date | str) -> TimelineSimulationResult:
        end_date = _coerce_date(target_date)
        if end_date is None:
            raise ValueError("target_date must be a valid date")

        start_date = self._get_current_date()
        if end_date < start_date:
            raise ValueError("target_date cannot be earlier than the current campaign date")

        state = self._load_state()
        indexes = self._build_indexes(state)

        changes: list[TimelineChange] = []
        resolved_events = 0
        escalated_factions = 0
        escalated_villains = 0
        advanced_projects = 0
        npc_movements = 0

        cursor = start_date + timedelta(days=1)
        while cursor <= end_date:
            day_changes, day_counts = self._advance_single_day(cursor, state, indexes)
            changes.extend(day_changes)
            resolved_events += day_counts["resolved_events"]
            escalated_factions += day_counts["escalated_factions"]
            escalated_villains += day_counts["escalated_villains"]
            advanced_projects += day_counts["advanced_projects"]
            npc_movements += day_counts["npc_movements"]
            cursor += timedelta(days=1)

        self._persist_state(state)
        self._set_current_date(end_date)

        gm_summary = self._build_gm_summary(start_date, end_date, changes)
        set_campaign_setting("timeline_last_summary", gm_summary)
        set_campaign_setting(
            "timeline_last_changes_json",
            json.dumps([asdict(change) for change in changes], ensure_ascii=False),
        )

        return TimelineSimulationResult(
            start_date=start_date,
            end_date=end_date,
            days_advanced=(end_date - start_date).days,
            resolved_events=resolved_events,
            escalated_factions=escalated_factions,
            escalated_villains=escalated_villains,
            advanced_projects=advanced_projects,
            npc_movements=npc_movements,
            change_count=len(changes),
            gm_summary=gm_summary,
            changes=changes,
        )

    def _advance_single_day(self, current_day: date, state: dict[str, list[dict]], indexes: dict[str, dict[str, dict]]) -> tuple[list[TimelineChange], dict[str, int]]:
        changes: list[TimelineChange] = []
        counts = {
            "resolved_events": 0,
            "escalated_factions": 0,
            "escalated_villains": 0,
            "advanced_projects": 0,
            "npc_movements": 0,
        }

        for event in state["events"]:
            if _coerce_date(event.get("Date")) != current_day:
                continue
            if str(event.get("Status") or "").strip().lower() in _COMPLETED_EVENT_STATUSES:
                continue
            if event.get("AutoResolve", True) is False:
                continue

            title = _text(event.get("Title") or event.get("Name") or "Scheduled Event")
            event["Status"] = "Resolved"
            event["Resolution"] = _append_paragraph(
                event.get("Resolution"),
                f"{current_day.isoformat()}: resolved automatically by the timeline simulator.",
            )
            change = self._record_change(
                changes,
                current_day,
                category="event",
                entity_type="events",
                entity_name=title,
                summary=f"Scheduled event resolved: {title}.",
                scenario_names=_coerce_list(event.get("Scenarios")),
                place_names=_coerce_list(event.get("Places")),
                npc_names=_coerce_list(event.get("NPCs")),
                map_names=_coerce_list(event.get("Maps")),
                clue_names=_coerce_list(event.get("Clues")),
            )
            self._apply_change_feedback(change, state, indexes)
            counts["resolved_events"] += 1

        for faction in state["factions"]:
            if _coerce_date(faction.get("NextEscalationDate")) != current_day:
                continue
            name = _text(faction.get("Name") or "Faction")
            agenda = _text(faction.get("Agenda") or faction.get("Description") or "Advance its agenda")
            stage = _int_value(faction.get("PlanStage")) + 1
            faction["PlanStage"] = stage
            faction["EscalationLevel"] = max(_int_value(faction.get("EscalationLevel")), stage)
            faction["LastEscalationDate"] = current_day.isoformat()
            cadence = max(1, _int_value(faction.get("EscalationCadenceDays"), default=7))
            faction["NextEscalationDate"] = (current_day + timedelta(days=cadence)).isoformat()
            faction["PlanHistory"] = _append_history(
                faction.get("PlanHistory"),
                {"date": current_day.isoformat(), "stage": stage, "summary": agenda},
            )
            change = self._record_change(
                changes,
                current_day,
                category="faction",
                entity_type="factions",
                entity_name=name,
                summary=f"{name} escalates to stage {stage}: {agenda}.",
                scenario_names=_coerce_list(faction.get("ActiveScenarios")) or _coerce_list(faction.get("Scenarios")),
                place_names=_coerce_list(faction.get("ControlledPlaces")) or _coerce_list(faction.get("Places")),
                npc_names=[],
                map_names=_coerce_list(faction.get("Maps")),
                clue_names=_coerce_list(faction.get("Clues")),
            )
            self._apply_change_feedback(change, state, indexes)
            counts["escalated_factions"] += 1

        for villain in state["villains"]:
            if _coerce_date(villain.get("NextEscalationDate")) != current_day:
                continue
            name = _text(villain.get("Name") or "Villain")
            agenda = _text(
                villain.get("CurrentObjective")
                or villain.get("Scheme")
                or villain.get("Description")
                or "Advance a villainous scheme"
            )
            level = _int_value(villain.get("EscalationLevel")) + 1
            villain["EscalationLevel"] = level
            villain["LastEscalationDate"] = current_day.isoformat()
            cadence = max(1, _int_value(villain.get("EscalationCadenceDays"), default=7))
            villain["NextEscalationDate"] = (current_day + timedelta(days=cadence)).isoformat()
            villain["SchemeHistory"] = _append_history(
                villain.get("SchemeHistory"),
                {"date": current_day.isoformat(), "level": level, "summary": agenda},
            )
            related_npcs = [name] + _coerce_list(villain.get("Lieutenants")) + _coerce_list(villain.get("NPCs"))
            change = self._record_change(
                changes,
                current_day,
                category="villain",
                entity_type="villains",
                entity_name=name,
                summary=f"{name} advances a villain plan to level {level}: {agenda}.",
                scenario_names=_coerce_list(villain.get("Scenarios")),
                place_names=_coerce_list(villain.get("Places")),
                npc_names=related_npcs,
                map_names=_coerce_list(villain.get("Maps")),
                clue_names=_coerce_list(villain.get("Clues")),
            )
            self._apply_change_feedback(change, state, indexes)
            self._upsert_villain_escalation_event(state, villain, current_day, agenda, level)
            counts["escalated_villains"] += 1

        for npc in state["npcs"]:
            if not _is_truthy(npc.get("IsVillain")):
                continue
            if _coerce_date(npc.get("NextEscalationDate")) != current_day:
                continue
            name = _text(npc.get("Name") or "Villain")
            agenda = _text(npc.get("Agenda") or npc.get("Role") or "Pursue a villainous objective")
            level = _int_value(npc.get("EscalationLevel")) + 1
            npc["EscalationLevel"] = level
            npc["LastEscalationDate"] = current_day.isoformat()
            cadence = max(1, _int_value(npc.get("EscalationCadenceDays"), default=7))
            npc["NextEscalationDate"] = (current_day + timedelta(days=cadence)).isoformat()
            npc["SchemeHistory"] = _append_history(
                npc.get("SchemeHistory"),
                {"date": current_day.isoformat(), "level": level, "summary": agenda},
            )
            change = self._record_change(
                changes,
                current_day,
                category="villain",
                entity_type="npcs",
                entity_name=name,
                summary=f"{name} advances a villain plan to level {level}: {agenda}.",
                scenario_names=_coerce_list(npc.get("LinkedScenarios")) or _coerce_list(npc.get("Scenarios")),
                place_names=_coerce_list([npc.get("CurrentLocation")]),
                npc_names=[name],
                map_names=_coerce_list(npc.get("Maps")),
                clue_names=_coerce_list(npc.get("Clues")),
            )
            self._apply_change_feedback(change, state, indexes)
            counts["escalated_villains"] += 1

        for base in state["bases"]:
            projects = _coerce_list(base.get("Projects"))
            if not projects:
                continue
            project_changed = False
            for project in projects:
                if not isinstance(project, dict):
                    continue
                if str(project.get("status") or "active").strip().lower() not in {"active", "in_progress", "planned"}:
                    continue
                start_on = _coerce_date(project.get("start_date"))
                if start_on is not None and start_on > current_day:
                    continue
                project["progress"] = _int_value(project.get("progress")) + max(1, _int_value(project.get("daily_progress"), default=1))
                required = max(1, _int_value(project.get("required"), default=1))
                if project["progress"] >= required:
                    project["progress"] = required
                    project["status"] = "completed"
                    project["completed_date"] = current_day.isoformat()
                else:
                    project["status"] = "active"
                project_changed = True
                project_name = _text(project.get("name") or "Base project")
                base_name = _text(base.get("Name") or "Base")
                summary = (
                    f"{base_name} project advanced: {project_name} "
                    f"({project['progress']}/{required})."
                )
                if project["status"] == "completed":
                    summary = f"{base_name} project completed: {project_name}."
                change = self._record_change(
                    changes,
                    current_day,
                    category="base_project",
                    entity_type="bases",
                    entity_name=base_name,
                    summary=summary,
                    scenario_names=_coerce_list(project.get("scenario")) or _coerce_list(project.get("scenarios")),
                    place_names=_coerce_list([base.get("Location")]) + _coerce_list(project.get("places")),
                    npc_names=_coerce_list(project.get("npcs")) + _coerce_list(base.get("Staff")),
                    map_names=_coerce_list(project.get("maps")) + _coerce_list(base.get("Maps")),
                    clue_names=_coerce_list(project.get("clues")),
                )
                self._apply_change_feedback(change, state, indexes)
                counts["advanced_projects"] += 1
            if project_changed:
                base["Projects"] = projects

        for npc in state["npcs"]:
            schedule = _coerce_list(npc.get("MovementSchedule"))
            if not schedule:
                continue
            schedule_changed = False
            for step in schedule:
                if not isinstance(step, dict):
                    continue
                if _is_truthy(step.get("resolved")):
                    continue
                if _coerce_date(step.get("date")) != current_day:
                    continue
                previous_location = _text(npc.get("CurrentLocation"))
                new_location = _text(step.get("place") or step.get("destination"))
                if not new_location:
                    continue
                npc["CurrentLocation"] = new_location
                step["resolved"] = True
                step["resolved_date"] = current_day.isoformat()
                schedule_changed = True
                name = _text(npc.get("Name") or "NPC")
                reason = _text(step.get("reason") or "scheduled movement")
                summary = f"{name} moves from {previous_location or 'an unknown location'} to {new_location}: {reason}."
                change = self._record_change(
                    changes,
                    current_day,
                    category="npc_movement",
                    entity_type="npcs",
                    entity_name=name,
                    summary=summary,
                    scenario_names=_coerce_list(step.get("scenarios")) or _coerce_list(npc.get("LinkedScenarios")),
                    place_names=[new_location] + _coerce_list([previous_location]),
                    npc_names=[name],
                    map_names=_coerce_list(step.get("maps")) + _coerce_list(npc.get("Maps")),
                    clue_names=_coerce_list(step.get("clues")) + _coerce_list(npc.get("Clues")),
                )
                self._apply_change_feedback(change, state, indexes, previous_location=previous_location)
                counts["npc_movements"] += 1
            if schedule_changed:
                npc["MovementSchedule"] = schedule

        return changes, counts

    def _apply_change_feedback(
        self,
        change: TimelineChange,
        state: dict[str, list[dict]],
        indexes: dict[str, dict[str, dict]],
        *,
        previous_location: str | None = None,
    ) -> None:
        payload = asdict(change)

        for scenario_name in change.related_scenarios:
            scenario = indexes["scenarios"].get(_normalize_key(scenario_name))
            if scenario is None:
                continue
            scenario["TimelineHistory"] = _append_history(scenario.get("TimelineHistory"), payload)
            scenario["LastTimelineUpdate"] = change.occurred_on
            scenario["GMNotes"] = _append_paragraph(scenario.get("GMNotes"), f"{change.occurred_on}: {change.summary}")

        for place_name in change.related_places:
            place = indexes["places"].get(_normalize_key(place_name))
            if place is None:
                continue
            place["WorldStateChanges"] = _append_history(place.get("WorldStateChanges"), payload)
            place["Situation"] = _append_paragraph(place.get("Situation"), f"{change.occurred_on}: {change.summary}")
            if change.category == "npc_movement":
                occupants = _coerce_list(place.get("Occupants"))
                for npc_name in change.related_npcs:
                    if _normalize_key(place_name) == _normalize_key(previous_location):
                        occupants = [entry for entry in occupants if _normalize_key(entry) != _normalize_key(npc_name)]
                    elif npc_name not in occupants:
                        occupants.append(npc_name)
                place["Occupants"] = _dedupe_strings(occupants)

        for map_name in change.related_maps:
            campaign_map = indexes["maps"].get(_normalize_key(map_name))
            if campaign_map is None:
                continue
            campaign_map["WorldStateChanges"] = _append_history(campaign_map.get("WorldStateChanges"), payload)
            campaign_map["DynamicNotes"] = _append_paragraph(campaign_map.get("DynamicNotes"), f"{change.occurred_on}: {change.summary}")

        for clue_name in change.related_clues:
            clue = indexes["clues"].get(_normalize_key(clue_name))
            if clue is None:
                continue
            clue["WorldStateChanges"] = _append_history(clue.get("WorldStateChanges"), payload)
            clue["Status"] = clue.get("Status") or "Active"
            clue["DiscoveryDate"] = clue.get("DiscoveryDate") or change.occurred_on

        if change.category == "event":
            for clue_name in change.related_clues:
                clue = indexes["clues"].get(_normalize_key(clue_name))
                if clue is None:
                    continue
                clue["Description"] = _append_paragraph(
                    clue.get("Description"),
                    f"Timeline update on {change.occurred_on}: {change.summary}",
                )

    def _record_change(
        self,
        changes: list[TimelineChange],
        current_day: date,
        *,
        category: str,
        entity_type: str,
        entity_name: str,
        summary: str,
        scenario_names: list[Any],
        place_names: list[Any],
        npc_names: list[Any],
        map_names: list[Any],
        clue_names: list[Any],
    ) -> TimelineChange:
        change = TimelineChange(
            occurred_on=current_day.isoformat(),
            category=category,
            entity_type=entity_type,
            entity_name=entity_name,
            summary=summary,
            related_places=_dedupe_strings(place_names),
            related_npcs=_dedupe_strings(npc_names),
            related_scenarios=_dedupe_strings(scenario_names),
            related_maps=_dedupe_strings(map_names),
            related_clues=_dedupe_strings(clue_names),
        )
        changes.append(change)
        return change

    def _build_gm_summary(self, start_date: date, end_date: date, changes: list[TimelineChange]) -> str:
        if not changes:
            return f"No world-state changes between {start_date.isoformat()} and {end_date.isoformat()}."

        headline = (
            f"Timeline advanced from {start_date.isoformat()} to {end_date.isoformat()} "
            f"with {len(changes)} world-state changes."
        )
        lines = [headline]
        for change in changes[:12]:
            lines.append(f"- {change.occurred_on}: {change.summary}")
        if len(changes) > 12:
            lines.append(f"- {len(changes) - 12} additional changes omitted from this short summary.")
        return "\n".join(lines)

    def _load_state(self) -> dict[str, list[dict]]:
        state: dict[str, list[dict]] = {}
        for slug in self.ENTITY_TYPES:
            wrapper = self._wrapper(slug)
            try:
                state[slug] = wrapper.load_items()
            except Exception:
                state[slug] = []
        return state

    def _persist_state(self, state: dict[str, list[dict]]) -> None:
        for slug, items in state.items():
            wrapper = self._wrapper(slug)
            wrapper.save_items(items, replace=True)

    def _build_indexes(self, state: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
        indexed: dict[str, dict[str, dict]] = {}
        for slug, items in state.items():
            key_field = "Title" if slug in {"scenarios", "informations"} else "Name"
            table = {}
            for item in items:
                key = _normalize_key(item.get(key_field))
                if key:
                    table[key] = item
            indexed[slug] = table
        return indexed

    def _wrapper(self, slug: str):
        wrapper = self._wrappers.get(slug)
        if wrapper is None:
            wrapper = GenericModelWrapper(slug)
            self._wrappers[slug] = wrapper
        return wrapper

    def _upsert_villain_escalation_event(
        self,
        state: dict[str, list[dict]],
        villain: dict[str, Any],
        current_day: date,
        agenda: str,
        level: int,
    ) -> None:
        events = state.setdefault("events", [])
        villain_name = _text(villain.get("Name") or "Villain")
        event_name = f"{villain_name} escalation {current_day.isoformat()}"
        payload = {
            "Name": event_name,
            "Title": f"{villain_name} escalation",
            "Date": current_day.isoformat(),
            "Type": "villain",
            "Color": "#A63DE0",
            "Status": "Escalated",
            "AutoResolve": False,
            "Resolution": "",
            "Places": _coerce_list(villain.get("Places")),
            "NPCs": _coerce_list(villain.get("Lieutenants")) + _coerce_list(villain.get("NPCs")),
            "Villains": [villain_name],
            "Creatures": _coerce_list(villain.get("Creatures")) + _coerce_list(villain.get("CreatureAgents")),
            "Scenarios": _coerce_list(villain.get("Scenarios")),
            "Informations": [],
            "Factions": _coerce_list(villain.get("Factions")),
            "Bases": [],
            "Maps": _coerce_list(villain.get("Maps")),
            "Clues": _coerce_list(villain.get("Clues")),
            "Objects": _coerce_list(villain.get("Objects")),
            "Notes": f"Escalation level {level}: {agenda}",
        }
        for index, event in enumerate(events):
            if _normalize_key(event.get("Name")) == _normalize_key(event_name):
                events[index] = payload
                return
        events.append(payload)

    @staticmethod
    def _get_current_date() -> date:
        stored = get_campaign_setting("timeline_current_date")
        return _coerce_date(stored) or date.today()

    @staticmethod
    def _set_current_date(value: date) -> None:
        set_campaign_setting("timeline_current_date", value.isoformat())


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    for fmt in ("%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                return decoded
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return [text]
    return [value]


def _append_history(existing: Any, entry: dict[str, Any]) -> list[dict[str, Any]]:
    history = _coerce_list(existing)
    history.append(entry)
    return history


def _append_paragraph(existing: Any, text: str) -> str:
    base = _text(existing)
    if not base:
        return text
    return f"{base}\n{text}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_key(value: Any) -> str:
    return _text(value).casefold()


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        text = _text(raw)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered
