from __future__ import annotations

from typing import Any

from modules.campaigns.services.ai.arc_scenario_entities import ENTITY_WRAPPER_SPECS
from modules.generic.generic_model_wrapper import GenericModelWrapper


class GeneratedScenarioPersistence:
    """Persist AI-generated scenarios and link saved titles back to their parent arcs."""

    def __init__(self, scenario_wrapper, entity_wrappers: dict[str, Any] | None = None):
        self.scenario_wrapper = scenario_wrapper
        self.entity_wrappers = entity_wrappers or {}

    def save_generated_arc_scenarios(
        self,
        generated_payload: dict[str, Any],
        arcs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        existing_titles = self._load_existing_titles()
        reserved_titles = set(existing_titles)
        saved_groups: list[dict[str, Any]] = []

        for group in generated_payload.get("arcs") or []:
            arc_name = str(group.get("arc_name") or "").strip()
            saved_scenarios: list[dict[str, Any]] = []
            for scenario in group.get("scenarios") or []:
                self._save_created_entities(scenario)
                payload = dict(scenario)
                payload.pop("EntityCreations", None)
                payload["Title"] = self._make_unique_title(payload.get("Title"), reserved_titles)
                reserved_titles.add(payload["Title"].casefold())
                self.scenario_wrapper.save_item(payload, key_field="Title")
                saved_scenarios.append(payload)
                self._append_title_to_parent_arc(arcs, arc_name, payload["Title"])
            saved_groups.append({"arc_name": arc_name, "scenarios": saved_scenarios})

        return saved_groups

    def _load_existing_titles(self) -> set[str]:
        try:
            items = self.scenario_wrapper.load_items() if self.scenario_wrapper else []
        except Exception:
            items = []
        titles: set[str] = set()
        for item in items or []:
            title = str(item.get("Title") or item.get("Name") or "").strip()
            if title:
                titles.add(title.casefold())
        return titles

    def _save_created_entities(self, scenario: dict[str, Any]) -> None:
        entity_creations = scenario.get("EntityCreations")
        if not isinstance(entity_creations, dict):
            return

        for entity_type, spec in ENTITY_WRAPPER_SPECS.items():
            records = entity_creations.get(entity_type)
            if not isinstance(records, list) or not records:
                continue

            wrapper = self._resolve_entity_wrapper(entity_type)
            key_field = spec["key_field"]
            existing_items = wrapper.load_items() if wrapper else []
            index = {
                str(item.get(key_field) or "").strip().casefold(): dict(item)
                for item in existing_items or []
                if isinstance(item, dict) and str(item.get(key_field) or "").strip()
            }
            updated = False
            for record in records:
                if not isinstance(record, dict):
                    continue
                name = str(record.get(key_field) or "").strip()
                if not name:
                    continue
                key = name.casefold()
                if key in index:
                    continue
                index[key] = dict(record)
                updated = True

            if updated and wrapper:
                wrapper.save_items(list(index.values()))

    def _resolve_entity_wrapper(self, entity_type: str):
        wrapper = self.entity_wrappers.get(entity_type)
        if wrapper is not None:
            return wrapper

        spec = ENTITY_WRAPPER_SPECS.get(entity_type)
        if not spec:
            return None

        wrapper = GenericModelWrapper(spec["wrapper"])
        self.entity_wrappers[entity_type] = wrapper
        return wrapper

    @staticmethod
    def _make_unique_title(title: Any, reserved_titles: set[str]) -> str:
        base_title = str(title or "").strip() or "Untitled Scenario"
        if base_title.casefold() not in reserved_titles:
            return base_title

        suffix = 2
        while True:
            candidate = f"{base_title} ({suffix})"
            if candidate.casefold() not in reserved_titles:
                return candidate
            suffix += 1

    @staticmethod
    def _append_title_to_parent_arc(arcs: list[dict[str, Any]], arc_name: str, title: str) -> None:
        target_key = str(arc_name or "").strip().casefold()
        for arc in arcs:
            if str(arc.get("name") or "").strip().casefold() != target_key:
                continue
            scenarios = arc.setdefault("scenarios", [])
            if title not in scenarios:
                scenarios.append(title)
            return
