from __future__ import annotations

from typing import Any

from modules.campaigns.services.ai.arc_scenario_entities import build_existing_entity_lookup
from modules.campaigns.services.ai.json_parsing import parse_json_relaxed
from modules.campaigns.services.ai.prompt_builders import build_arc_scenario_expansion_prompt


class ArcScenarioExpansionValidationError(ValueError):
    """Raised when arc-to-scenario expansion inputs or outputs are invalid."""


class ArcScenarioExpansionService:
    """Generate exactly two new scenario payloads for each existing campaign arc."""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    def generate_scenarios(self, foundation: dict[str, Any], arcs: list[dict[str, Any]]) -> dict[str, Any]:
        normalized_arcs = self._normalize_input_arcs(arcs)
        existing_entities = build_existing_entity_lookup(foundation)
        prompt = build_arc_scenario_expansion_prompt(foundation=foundation, arcs=normalized_arcs)
        messages = [
            {
                "role": "system",
                "content": "Write tabletop RPG scenarios and return strict JSON only.",
            },
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(2):
            raw_response = self.ai_client.chat(messages)
            try:
                parsed = parse_json_relaxed(raw_response)
                return self._normalize_generated_payload(
                    parsed,
                    normalized_arcs,
                    existing_entities=existing_entities,
                )
            except Exception as exc:
                last_error = exc
                if attempt == 1:
                    raise
                messages = [
                    *messages,
                    {"role": "assistant", "content": str(raw_response)},
                    {
                        "role": "user",
                        "content": (
                            "Your previous JSON did not satisfy the scenario-generation constraints. "
                            f"Fix it and return strict JSON only. Error: {exc}. "
                            "Ensure every arc appears exactly once and contains exactly 2 scenario payloads."
                        ),
                    },
                ]

        raise RuntimeError(f"Scenario expansion failed: {last_error}")

    def _normalize_input_arcs(self, arcs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, arc in enumerate(arcs or [], start=1):
            if not isinstance(arc, dict):
                raise ArcScenarioExpansionValidationError(f"Arc #{index} must be an object")

            name = str(arc.get("name") or "").strip()
            if not name:
                raise ArcScenarioExpansionValidationError(f"Arc #{index} is missing a name")

            linked_scenarios = [str(title).strip() for title in (arc.get("scenarios") or []) if str(title).strip()]
            if not linked_scenarios:
                raise ArcScenarioExpansionValidationError(
                    f"Arc '{name}' must include at least 1 linked scenario before generation"
                )

            normalized.append(
                {
                    "name": name,
                    "summary": str(arc.get("summary") or arc.get("description") or "").strip(),
                    "objective": str(arc.get("objective") or "").strip(),
                    "thread": str(arc.get("thread") or "").strip(),
                    "scenarios": linked_scenarios,
                }
            )

        if not normalized:
            raise ArcScenarioExpansionValidationError("At least one arc is required for scenario generation")
        return normalized

    def _normalize_generated_payload(
        self,
        payload: Any,
        arcs: list[dict[str, Any]],
        *,
        existing_entities: dict[str, set[str]] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ArcScenarioExpansionValidationError("AI scenario generation must return a JSON object")

        raw_arc_groups = payload.get("arcs")
        if not isinstance(raw_arc_groups, list):
            raise ArcScenarioExpansionValidationError("The 'arcs' field must be a JSON array")

        expected_arc_names = [arc["name"] for arc in arcs]
        expected_lookup = {name.casefold(): name for name in expected_arc_names}
        arc_context_lookup = {arc["name"].casefold(): arc for arc in arcs}
        seen_arc_names: set[str] = set()
        used_titles: set[str] = set()
        normalized_groups: list[dict[str, Any]] = []

        for raw_group in raw_arc_groups:
            if not isinstance(raw_group, dict):
                raise ArcScenarioExpansionValidationError("Each generated arc group must be an object")

            raw_arc_name = str(raw_group.get("arc_name") or "").strip()
            if not raw_arc_name:
                raise ArcScenarioExpansionValidationError("Each generated arc group must include 'arc_name'")

            arc_key = raw_arc_name.casefold()
            if arc_key not in expected_lookup:
                raise ArcScenarioExpansionValidationError(f"Unknown arc in generated payload: {raw_arc_name}")
            if arc_key in seen_arc_names:
                raise ArcScenarioExpansionValidationError(f"Arc '{raw_arc_name}' appears more than once")
            seen_arc_names.add(arc_key)

            raw_scenarios = raw_group.get("scenarios")
            if not isinstance(raw_scenarios, list):
                raise ArcScenarioExpansionValidationError(
                    f"Arc '{raw_arc_name}' must include a 'scenarios' array"
                )
            if len(raw_scenarios) != 2:
                raise ArcScenarioExpansionValidationError(
                    f"Arc '{raw_arc_name}' must contain exactly 2 generated scenarios"
                )

            normalized_scenarios = [
                self._normalize_scenario_payload(
                    scenario_payload,
                    parent_arc=arc_context_lookup[arc_key],
                    used_titles=used_titles,
                    existing_entities=existing_entities,
                )
                for scenario_payload in raw_scenarios
            ]
            normalized_groups.append(
                {
                    "arc_name": expected_lookup[arc_key],
                    "scenarios": normalized_scenarios,
                }
            )

        if seen_arc_names != set(expected_lookup):
            missing = [name for name in expected_arc_names if name.casefold() not in seen_arc_names]
            raise ArcScenarioExpansionValidationError(
                f"Generated payload is missing arc groups for: {', '.join(missing)}"
            )

        return {"arcs": normalized_groups}

    @staticmethod
    def _normalize_scenario_payload(
        payload: Any,
        *,
        parent_arc: dict[str, Any],
        used_titles: set[str],
        existing_entities: dict[str, set[str]] | None,
    ) -> dict[str, Any]:
        parent_arc_name = parent_arc["name"]
        if not isinstance(payload, dict):
            raise ArcScenarioExpansionValidationError(
                f"Generated scenario for arc '{parent_arc_name}' must be an object"
            )

        title = str(payload.get("Title") or "").strip()
        if not title:
            raise ArcScenarioExpansionValidationError(
                f"Generated scenario for arc '{parent_arc_name}' is missing a Title"
            )

        title_key = title.casefold()
        if title_key in used_titles:
            raise ArcScenarioExpansionValidationError(f"Duplicate generated scenario title: {title}")
        used_titles.add(title_key)

        summary = str(payload.get("Summary") or "").strip()
        secrets = str(payload.get("Secrets") or "").strip()
        traceability_block = ArcScenarioExpansionService._build_traceability_block(parent_arc)
        entity_creations = ArcScenarioExpansionService._normalize_entity_creations(payload.get("EntityCreations"))

        scenes = ArcScenarioExpansionService._normalize_string_list(payload.get("Scenes"))
        if len(scenes) < 3:
            raise ArcScenarioExpansionValidationError(
                f"Generated scenario '{title}' for arc '{parent_arc_name}' must include at least 3 scenes"
            )

        places = ArcScenarioExpansionService._normalize_string_list(payload.get("Places"))
        npcs = ArcScenarioExpansionService._normalize_string_list(payload.get("NPCs"))
        villains = ArcScenarioExpansionService._normalize_string_list(payload.get("Villains"))
        creatures = ArcScenarioExpansionService._normalize_string_list(payload.get("Creatures"))
        factions = ArcScenarioExpansionService._normalize_string_list(payload.get("Factions"))
        objects = ArcScenarioExpansionService._normalize_string_list(payload.get("Objects"))

        ArcScenarioExpansionService._backfill_missing_entity_creations(
            title=title,
            summary=summary,
            parent_arc_name=parent_arc_name,
            places=places,
            npcs=npcs,
            villains=villains,
            creatures=creatures,
            factions=factions,
            entity_creations=entity_creations,
            existing_entities=existing_entities,
        )

        places = ArcScenarioExpansionService._ensure_created_links_present(places, entity_creations["places"])
        villains = ArcScenarioExpansionService._ensure_created_links_present(villains, entity_creations["villains"])
        factions = ArcScenarioExpansionService._ensure_created_links_present(factions, entity_creations["factions"])
        npcs = ArcScenarioExpansionService._ensure_created_links_present(npcs, entity_creations["npcs"])
        creatures = ArcScenarioExpansionService._ensure_created_links_present(creatures, entity_creations["creatures"])

        if not places:
            raise ArcScenarioExpansionValidationError(
                f"Generated scenario '{title}' for arc '{parent_arc_name}' must include at least 1 place"
            )
        if not villains:
            raise ArcScenarioExpansionValidationError(
                f"Generated scenario '{title}' for arc '{parent_arc_name}' must include at least 1 villain"
            )
        if not factions:
            raise ArcScenarioExpansionValidationError(
                f"Generated scenario '{title}' for arc '{parent_arc_name}' must include at least 1 faction"
            )

        ArcScenarioExpansionService._validate_new_links_are_defined(
            title=title,
            field_name="Places",
            entity_type="places",
            values=places,
            entity_creations=entity_creations,
            existing_entities=existing_entities,
        )
        ArcScenarioExpansionService._validate_new_links_are_defined(
            title=title,
            field_name="Villains",
            entity_type="villains",
            values=villains,
            entity_creations=entity_creations,
            existing_entities=existing_entities,
        )
        ArcScenarioExpansionService._validate_new_links_are_defined(
            title=title,
            field_name="Factions",
            entity_type="factions",
            values=factions,
            entity_creations=entity_creations,
            existing_entities=existing_entities,
        )
        ArcScenarioExpansionService._validate_new_links_are_defined(
            title=title,
            field_name="NPCs",
            entity_type="npcs",
            values=npcs,
            entity_creations=entity_creations,
            existing_entities=existing_entities,
        )
        ArcScenarioExpansionService._validate_new_links_are_defined(
            title=title,
            field_name="Creatures",
            entity_type="creatures",
            values=creatures,
            entity_creations=entity_creations,
            existing_entities=existing_entities,
        )

        if parent_arc_name and parent_arc_name not in summary:
            summary = f"{summary}\n\nContinues arc: {parent_arc_name}." if summary else f"Continues arc: {parent_arc_name}."
        if traceability_block not in secrets:
            secrets = f"{secrets}\n\n{traceability_block}".strip()

        return {
            "Title": title,
            "Summary": summary,
            "Secrets": secrets,
            "Scenes": scenes,
            "Places": places,
            "NPCs": npcs,
            "Villains": villains,
            "Creatures": creatures,
            "Factions": factions,
            "Objects": objects,
            "EntityCreations": entity_creations,
        }

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise ArcScenarioExpansionValidationError("Scenario link fields must be JSON arrays")
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _normalize_entity_creations(value: Any) -> dict[str, list[dict[str, Any]]]:
        raw = value if isinstance(value, dict) else {}
        return {
            "villains": ArcScenarioExpansionService._normalize_created_villains(raw.get("villains")),
            "factions": ArcScenarioExpansionService._normalize_created_factions(raw.get("factions")),
            "places": ArcScenarioExpansionService._normalize_created_places(raw.get("places")),
            "npcs": ArcScenarioExpansionService._normalize_created_npcs(raw.get("npcs")),
            "creatures": ArcScenarioExpansionService._normalize_created_creatures(raw.get("creatures")),
        }

    @staticmethod
    def _ensure_created_links_present(values: list[str], created_records: list[dict[str, Any]]) -> list[str]:
        normalized = list(values)
        seen = {value.casefold() for value in normalized}
        for record in created_records:
            name = str(record.get("Name") or "").strip()
            if not name or name.casefold() in seen:
                continue
            normalized.append(name)
            seen.add(name.casefold())
        return normalized

    @staticmethod
    def _validate_new_links_are_defined(
        *,
        title: str,
        field_name: str,
        entity_type: str,
        values: list[str],
        entity_creations: dict[str, list[dict[str, Any]]],
        existing_entities: dict[str, set[str]] | None,
    ) -> None:
        if existing_entities is None:
            return

        known_existing = existing_entities.get(entity_type, set())
        known_created = {
            str(item.get("Name") or "").strip().casefold()
            for item in entity_creations.get(entity_type) or []
            if str(item.get("Name") or "").strip()
        }
        missing = [
            value for value in values
            if value.casefold() not in known_existing and value.casefold() not in known_created
        ]
        if missing:
            raise ArcScenarioExpansionValidationError(
                f"Scenario '{title}' links unknown {field_name}: {', '.join(missing)}. "
                "Add them to EntityCreations or reuse existing catalog entities."
            )

    @staticmethod
    def _backfill_missing_entity_creations(
        *,
        title: str,
        summary: str,
        parent_arc_name: str,
        places: list[str],
        npcs: list[str],
        villains: list[str],
        creatures: list[str],
        factions: list[str],
        entity_creations: dict[str, list[dict[str, Any]]],
        existing_entities: dict[str, set[str]] | None,
    ) -> None:
        if existing_entities is None:
            return

        scenario_context = {
            "title": title,
            "summary": summary,
            "parent_arc_name": parent_arc_name,
        }
        for entity_type, values in (
            ("places", places),
            ("npcs", npcs),
            ("villains", villains),
            ("creatures", creatures),
            ("factions", factions),
        ):
            ArcScenarioExpansionService._append_missing_entity_creations(
                entity_type=entity_type,
                values=values,
                entity_creations=entity_creations,
                existing_entities=existing_entities,
                scenario_context=scenario_context,
            )

    @staticmethod
    def _append_missing_entity_creations(
        *,
        entity_type: str,
        values: list[str],
        entity_creations: dict[str, list[dict[str, Any]]],
        existing_entities: dict[str, set[str]],
        scenario_context: dict[str, str],
    ) -> None:
        known_existing = existing_entities.get(entity_type, set())
        created_records = entity_creations.setdefault(entity_type, [])
        known_created = {
            str(item.get("Name") or "").strip().casefold()
            for item in created_records
            if str(item.get("Name") or "").strip()
        }
        for value in values:
            key = value.casefold()
            if key in known_existing or key in known_created:
                continue
            created_records.append(
                ArcScenarioExpansionService._build_placeholder_entity_record(
                    entity_type=entity_type,
                    name=value,
                    title=scenario_context["title"],
                    summary=scenario_context["summary"],
                    parent_arc_name=scenario_context["parent_arc_name"],
                )
            )
            known_created.add(key)

    @staticmethod
    def _build_placeholder_entity_record(
        *,
        entity_type: str,
        name: str,
        title: str,
        summary: str,
        parent_arc_name: str,
    ) -> dict[str, Any]:
        summary_text = summary.strip() or f"Auto-created from generated scenario '{title}'."
        arc_suffix = f" for arc '{parent_arc_name}'" if parent_arc_name else ""

        if entity_type == "villains":
            return {
                "Name": name,
                "Title": "",
                "Archetype": "",
                "ThreatLevel": "",
                "Description": summary_text,
                "Scheme": f"Auto-created from generated scenario '{title}'{arc_suffix}.",
                "CurrentObjective": "",
                "Secrets": "",
                "Factions": [],
                "Lieutenants": [],
                "CreatureAgents": [],
            }
        if entity_type == "factions":
            return {
                "Name": name,
                "Description": summary_text,
                "Secrets": f"Auto-created from generated scenario '{title}'{arc_suffix}.",
                "Villains": [],
            }
        if entity_type == "places":
            return {
                "Name": name,
                "Description": summary_text,
                "Secrets": f"Auto-created from generated scenario '{title}'{arc_suffix}.",
                "NPCs": [],
                "Villains": [],
            }
        if entity_type == "npcs":
            return {
                "Name": name,
                "Role": "",
                "Description": summary_text,
                "Secret": "",
                "Motivation": "",
                "Background": f"Auto-created from generated scenario '{title}'{arc_suffix}.",
                "Personality": "",
                "Factions": [],
            }
        if entity_type == "creatures":
            return {
                "Name": name,
                "Type": "",
                "Description": summary_text,
                "Weakness": "",
                "Powers": "",
            }
        return {"Name": name}

    @staticmethod
    def _normalize_created_villains(value: Any) -> list[dict[str, Any]]:
        records = ArcScenarioExpansionService._normalize_created_records(value, "villains")
        return [
            {
                "Name": record["Name"],
                "Title": str(record.get("Title") or "").strip(),
                "Archetype": str(record.get("Archetype") or "").strip(),
                "ThreatLevel": str(record.get("ThreatLevel") or "").strip(),
                "Description": str(record.get("Description") or "").strip(),
                "Scheme": str(record.get("Scheme") or "").strip(),
                "CurrentObjective": str(record.get("CurrentObjective") or "").strip(),
                "Secrets": str(record.get("Secrets") or "").strip(),
                "Factions": ArcScenarioExpansionService._normalize_string_list(record.get("Factions")),
                "Lieutenants": ArcScenarioExpansionService._normalize_string_list(record.get("Lieutenants")),
                "CreatureAgents": ArcScenarioExpansionService._normalize_string_list(record.get("CreatureAgents")),
            }
            for record in records
        ]

    @staticmethod
    def _normalize_created_factions(value: Any) -> list[dict[str, Any]]:
        records = ArcScenarioExpansionService._normalize_created_records(value, "factions")
        return [
            {
                "Name": record["Name"],
                "Description": str(record.get("Description") or "").strip(),
                "Secrets": str(record.get("Secrets") or "").strip(),
                "Villains": ArcScenarioExpansionService._normalize_string_list(record.get("Villains")),
            }
            for record in records
        ]

    @staticmethod
    def _normalize_created_places(value: Any) -> list[dict[str, Any]]:
        records = ArcScenarioExpansionService._normalize_created_records(value, "places")
        return [
            {
                "Name": record["Name"],
                "Description": str(record.get("Description") or "").strip(),
                "Secrets": str(record.get("Secrets") or "").strip(),
                "NPCs": ArcScenarioExpansionService._normalize_string_list(record.get("NPCs")),
                "Villains": ArcScenarioExpansionService._normalize_string_list(record.get("Villains")),
            }
            for record in records
        ]

    @staticmethod
    def _normalize_created_npcs(value: Any) -> list[dict[str, Any]]:
        records = ArcScenarioExpansionService._normalize_created_records(value, "npcs")
        return [
            {
                "Name": record["Name"],
                "Role": str(record.get("Role") or "").strip(),
                "Description": str(record.get("Description") or "").strip(),
                "Secret": str(record.get("Secret") or "").strip(),
                "Motivation": str(record.get("Motivation") or "").strip(),
                "Background": str(record.get("Background") or "").strip(),
                "Personality": str(record.get("Personality") or "").strip(),
                "Factions": ArcScenarioExpansionService._normalize_string_list(record.get("Factions")),
            }
            for record in records
        ]

    @staticmethod
    def _normalize_created_creatures(value: Any) -> list[dict[str, Any]]:
        records = ArcScenarioExpansionService._normalize_created_records(value, "creatures")
        return [
            {
                "Name": record["Name"],
                "Type": str(record.get("Type") or "").strip(),
                "Description": str(record.get("Description") or "").strip(),
                "Weakness": str(record.get("Weakness") or "").strip(),
                "Powers": str(record.get("Powers") or "").strip(),
            }
            for record in records
        ]

    @staticmethod
    def _normalize_created_records(value: Any, entity_type: str) -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise ArcScenarioExpansionValidationError(
                f"EntityCreations.{entity_type} must be a JSON array"
            )

        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in value:
            if not isinstance(record, dict):
                raise ArcScenarioExpansionValidationError(
                    f"EntityCreations.{entity_type} entries must be JSON objects"
                )
            name = str(record.get("Name") or "").strip()
            if not name:
                raise ArcScenarioExpansionValidationError(
                    f"EntityCreations.{entity_type} entries must include a Name"
                )
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"Name": name, **record})
        return normalized

    @staticmethod
    def _build_traceability_block(parent_arc: dict[str, Any]) -> str:
        source_scenarios = ", ".join(parent_arc.get("scenarios") or []) or "None"
        thread = str(parent_arc.get("thread") or "").strip() or "Unspecified"
        return (
            "Arc Context:\n"
            f"- Parent arc: {parent_arc['name']}\n"
            f"- Inherited thread: {thread}\n"
            f"- Source scenarios: {source_scenarios}"
        )
