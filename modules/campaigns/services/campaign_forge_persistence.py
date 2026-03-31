"""Persistence helpers for campaign forge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.campaigns.services.ai.arc_scenario_entities import ENTITY_WRAPPER_SPECS
from modules.generic.generic_model_wrapper import GenericModelWrapper

SAVE_MODE_REPLACE_GENERATED_ONLY = "replace_generated_only"
SAVE_MODE_MERGE_KEEP_EXISTING = "merge_keep_existing"
SAVE_MODE_MERGE_OVERWRITE_ON_CONFLICT = "merge_overwrite_on_conflict"
SUPPORTED_SAVE_MODES = {
    SAVE_MODE_REPLACE_GENERATED_ONLY,
    SAVE_MODE_MERGE_KEEP_EXISTING,
    SAVE_MODE_MERGE_OVERWRITE_ON_CONFLICT,
}


class CampaignForgePersistenceError(RuntimeError):
    """Raised when one or more persistence steps fail during campaign forging."""


@dataclass
class _ScenarioOperation:
    arc_name: str
    source_title: str
    final_title: str
    action: str
    reason: str | None
    payload: dict[str, Any]


class CampaignForgePersistence:
    """Persist campaign metadata + generated scenarios with previewable dry-runs."""

    def __init__(
        self,
        scenario_wrapper,
        *,
        campaign_wrapper=None,
        entity_wrappers: dict[str, Any] | None = None,
    ):
        """Initialize the CampaignForgePersistence instance."""
        self.scenario_wrapper = scenario_wrapper
        self.campaign_wrapper = campaign_wrapper
        self.entity_wrappers = entity_wrappers or {}
        self.unsaved_generated_payload: dict[str, Any] | None = None
        self.last_error_summary: str | None = None

    def build_dry_run_report(
        self,
        generated_payload: dict[str, Any],
        arcs: list[dict[str, Any]],
        *,
        save_mode: str,
    ) -> dict[str, Any]:
        """Build dry run report."""
        save_mode = self._validate_save_mode(save_mode)
        existing_titles = self._load_existing_titles()
        operations = self._plan_operations(generated_payload, existing_titles, save_mode)
        arc_link_updates = self._plan_arc_link_updates(arcs, operations, save_mode)

        scenarios_summary = {"new": 0, "updated": 0, "skipped": 0}
        for op in operations:
            if op.action in scenarios_summary:
                scenarios_summary[op.action] += 1

        return {
            "save_mode": save_mode,
            "scenarios": {
                "summary": scenarios_summary,
                "items": [
                    {
                        "arc_name": op.arc_name,
                        "source_title": op.source_title,
                        "final_title": op.final_title,
                        "action": op.action,
                        "reason": op.reason,
                    }
                    for op in operations
                ],
            },
            "arc_linkage": arc_link_updates,
        }

    def save_from_dry_run(
        self,
        generated_payload: dict[str, Any],
        arcs: list[dict[str, Any]],
        dry_run_report: dict[str, Any],
        *,
        campaign_metadata: dict[str, Any] | None = None,
        campaign_original_key: str | None = None,
    ) -> dict[str, Any]:
        """Save from dry run."""
        self.unsaved_generated_payload = None
        self.last_error_summary = None

        operations = self._operations_from_report(generated_payload, dry_run_report)
        failures: list[dict[str, str]] = []
        saved_groups: list[dict[str, Any]] = []

        if campaign_metadata:
            try:
                # Keep from dry run resilient if this step fails.
                if not self.campaign_wrapper:
                    raise CampaignForgePersistenceError("campaign_wrapper is required to persist campaign metadata")
                self.campaign_wrapper.save_item(
                    campaign_metadata,
                    key_field="Name",
                    original_key_value=campaign_original_key,
                )
            except Exception as exc:
                failures.append(
                    {
                        "phase": "campaign_metadata",
                        "arc_name": "",
                        "title": str(campaign_metadata.get("Name") or ""),
                        "error": str(exc),
                    }
                )

        grouped_saved: dict[str, list[dict[str, Any]]] = {}
        for op in operations:
            # Process each op from operations.
            if op.action == "skipped":
                continue
            try:
                # Keep from dry run resilient if this step fails.
                self._save_created_entities(op.payload)
                scenario_payload = dict(op.payload)
                scenario_payload.pop("EntityCreations", None)
                scenario_payload["Title"] = op.final_title
                self.scenario_wrapper.save_item(scenario_payload, key_field="Title")
                grouped_saved.setdefault(op.arc_name, []).append(scenario_payload)
            except Exception as exc:
                failures.append(
                    {
                        "phase": "scenario",
                        "arc_name": op.arc_name,
                        "title": op.final_title,
                        "error": str(exc),
                    }
                )

        for arc_name, scenarios in grouped_saved.items():
            saved_groups.append({"arc_name": arc_name, "scenarios": scenarios})

        if not failures:
            self._apply_arc_link_updates(arcs, dry_run_report.get("arc_linkage") or {})
            return {
                "saved_groups": saved_groups,
                "dry_run_report": dry_run_report,
                "failures": [],
            }

        self.unsaved_generated_payload = generated_payload
        self.last_error_summary = self._build_error_summary(failures)
        raise CampaignForgePersistenceError(self.last_error_summary)

    def save(
        self,
        generated_payload: dict[str, Any],
        arcs: list[dict[str, Any]],
        *,
        save_mode: str,
        campaign_metadata: dict[str, Any] | None = None,
        campaign_original_key: str | None = None,
    ) -> dict[str, Any]:
        """Save the operation."""
        dry_run_report = self.build_dry_run_report(generated_payload, arcs, save_mode=save_mode)
        return self.save_from_dry_run(
            generated_payload,
            arcs,
            dry_run_report,
            campaign_metadata=campaign_metadata,
            campaign_original_key=campaign_original_key,
        )

    def _operations_from_report(self, generated_payload: dict[str, Any], report: dict[str, Any]) -> list[_ScenarioOperation]:
        """Internal helper for operations from report."""
        item_rows = report.get("scenarios", {}).get("items", [])
        payload_rows = {}
        for group in generated_payload.get("arcs") or []:
            # Process each group from generated_payload.get('arcs') or [].
            arc_name = str(group.get("arc_name") or "").strip()
            for scenario in group.get("scenarios") or []:
                title = str(scenario.get("Title") or "Untitled Scenario").strip() or "Untitled Scenario"
                payload_rows[(arc_name.casefold(), title.casefold())] = dict(scenario)

        operations: list[_ScenarioOperation] = []
        for row in item_rows:
            arc_name = str(row.get("arc_name") or "").strip()
            source_title = str(row.get("source_title") or "").strip()
            payload = payload_rows.get((arc_name.casefold(), source_title.casefold()), {"Title": source_title})
            operations.append(
                _ScenarioOperation(
                    arc_name=arc_name,
                    source_title=source_title,
                    final_title=str(row.get("final_title") or source_title),
                    action=str(row.get("action") or "skipped"),
                    reason=row.get("reason"),
                    payload=payload,
                )
            )
        return operations

    def _plan_operations(
        self,
        generated_payload: dict[str, Any],
        existing_titles: set[str],
        save_mode: str,
    ) -> list[_ScenarioOperation]:
        """Internal helper for plan operations."""
        operations: list[_ScenarioOperation] = []
        reserved_titles = set(existing_titles)

        for group in generated_payload.get("arcs") or []:
            # Process each group from generated_payload.get('arcs') or [].
            arc_name = str(group.get("arc_name") or "").strip()
            for raw_scenario in group.get("scenarios") or []:
                # Process each raw_scenario from group.get('scenarios') or [].
                payload = dict(raw_scenario) if isinstance(raw_scenario, dict) else {}
                source_title = str(payload.get("Title") or "Untitled Scenario").strip() or "Untitled Scenario"
                final_title = source_title
                reason = None
                existing_conflict = source_title.casefold() in existing_titles

                if existing_conflict and save_mode == SAVE_MODE_MERGE_KEEP_EXISTING:
                    final_title = self._make_unique_title(source_title, reserved_titles)
                    reason = "duplicate_title_renamed"

                if final_title.casefold() in reserved_titles:
                    if save_mode == SAVE_MODE_MERGE_OVERWRITE_ON_CONFLICT and final_title.casefold() in existing_titles:
                        action = "updated"
                        reason = reason or "conflict_overwritten"
                    else:
                        final_title = self._make_unique_title(final_title, reserved_titles)
                        action = "new"
                        reason = reason or "duplicate_title_renamed"
                else:
                    action = "updated" if (existing_conflict and save_mode != SAVE_MODE_MERGE_KEEP_EXISTING) else "new"

                if not source_title:
                    action = "skipped"
                    reason = "missing_title"

                operations.append(
                    _ScenarioOperation(
                        arc_name=arc_name,
                        source_title=source_title,
                        final_title=final_title,
                        action=action,
                        reason=reason,
                        payload=payload,
                    )
                )
                if action != "skipped":
                    reserved_titles.add(final_title.casefold())

        return operations

    def _plan_arc_link_updates(
        self,
        arcs: list[dict[str, Any]],
        operations: list[_ScenarioOperation],
        save_mode: str,
    ) -> dict[str, Any]:
        """Internal helper for plan arc link updates."""
        planned_titles_by_arc: dict[str, list[str]] = {}
        for op in operations:
            # Process each op from operations.
            if op.action == "skipped":
                continue
            planned_titles_by_arc.setdefault(op.arc_name.casefold(), []).append(op.final_title)

        updates: list[dict[str, Any]] = []
        for arc in arcs:
            # Process each arc from arcs.
            arc_name = str(arc.get("name") or "").strip()
            key = arc_name.casefold()
            existing_titles = list(arc.get("scenarios") or [])
            generated_titles = planned_titles_by_arc.get(key, [])
            if save_mode == SAVE_MODE_REPLACE_GENERATED_ONLY:
                # Handle the branch where save_mode == SAVE_MODE_REPLACE_GENERATED_ONLY.
                next_titles = generated_titles
            else:
                next_titles = list(existing_titles)
                for title in generated_titles:
                    if title not in next_titles:
                        next_titles.append(title)

            if next_titles != existing_titles:
                updates.append({"arc_name": arc_name, "before": existing_titles, "after": next_titles})

        return {
            "summary": {
                "updated": len(updates),
                "unchanged": max(0, len(arcs) - len(updates)),
            },
            "items": updates,
        }

    @staticmethod
    def _apply_arc_link_updates(arcs: list[dict[str, Any]], arc_linkage_report: dict[str, Any]) -> None:
        """Apply arc link updates."""
        updates_by_arc = {
            str(row.get("arc_name") or "").casefold(): list(row.get("after") or [])
            for row in arc_linkage_report.get("items") or []
        }
        for arc in arcs:
            # Process each arc from arcs.
            key = str(arc.get("name") or "").strip().casefold()
            if key in updates_by_arc:
                arc["scenarios"] = updates_by_arc[key]

    def _load_existing_titles(self) -> set[str]:
        """Load existing titles."""
        try:
            items = self.scenario_wrapper.load_items() if self.scenario_wrapper else []
        except Exception:
            items = []

        titles: set[str] = set()
        for item in items or []:
            # Process each item from items or [].
            title = str(item.get("Title") or item.get("Name") or "").strip()
            if title:
                titles.add(title.casefold())
        return titles

    def _save_created_entities(self, scenario: dict[str, Any]) -> None:
        """Save created entities."""
        entity_creations = scenario.get("EntityCreations")
        if not isinstance(entity_creations, dict):
            return

        for entity_type, spec in ENTITY_WRAPPER_SPECS.items():
            # Process each (entity_type, spec) from ENTITY_WRAPPER_SPECS.items().
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
                # Process each record from records.
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
        """Resolve entity wrapper."""
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
    def _build_error_summary(failures: list[dict[str, str]]) -> str:
        """Build error summary."""
        lines = [f"{len(failures)} persistence operation(s) failed:"]
        for failure in failures:
            phase = failure.get("phase") or "unknown"
            arc_name = failure.get("arc_name") or "n/a"
            title = failure.get("title") or "n/a"
            error = failure.get("error") or "Unknown error"
            lines.append(f"- phase={phase}, arc={arc_name}, title={title}: {error}")
        lines.append("Generated payload was kept in memory for retry/export.")
        return "\n".join(lines)

    @staticmethod
    def _make_unique_title(title: Any, reserved_titles: set[str]) -> str:
        """Internal helper for make unique title."""
        base_title = str(title or "").strip() or "Untitled Scenario"
        if base_title.casefold() not in reserved_titles:
            return base_title

        suffix = 2
        while True:
            # Keep looping while True.
            candidate = f"{base_title} ({suffix})"
            if candidate.casefold() not in reserved_titles:
                return candidate
            suffix += 1

    @staticmethod
    def _validate_save_mode(save_mode: str) -> str:
        """Validate save mode."""
        normalized = str(save_mode or "").strip()
        if normalized not in SUPPORTED_SAVE_MODES:
            supported = ", ".join(sorted(SUPPORTED_SAVE_MODES))
            raise ValueError(f"Unsupported save_mode '{save_mode}'. Expected one of: {supported}")
        return normalized
