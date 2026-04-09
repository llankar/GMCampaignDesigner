"""GM Screen 2-specific mapping from scenario records to domain models."""

from __future__ import annotations

from modules.scenarios.gm_screen2.domain.models import PanelPayload, ScenarioSummary


class ScenarioRecordMapper:
    """Map existing scenario dictionaries to GM Screen 2 domain entities."""

    def to_summary(self, record: dict) -> ScenarioSummary:
        """Map a persistence record to an immutable summary."""
        title = str(record.get("Title") or record.get("Name") or "Untitled Scenario").strip()
        scenario_id = str(record.get("id") or title)
        summary = str(record.get("Summary") or record.get("Description") or "").strip()
        raw_tags = record.get("Tags") or record.get("tags") or []
        if isinstance(raw_tags, str):
            tags = tuple(token.strip() for token in raw_tags.split(",") if token.strip())
        else:
            tags = tuple(str(tag).strip() for tag in raw_tags if str(tag).strip())
        return ScenarioSummary(scenario_id=scenario_id, title=title, summary=summary, tags=tags)

    def to_panel_payloads(self, record: dict, scenario: ScenarioSummary) -> dict[str, PanelPayload]:
        """Build default payloads for all desktop panel types."""
        notes = str(record.get("Notes") or record.get("GM Notes") or "").strip()
        timeline = str(record.get("Timeline") or "").strip()
        entities = self._format_entities(record)
        quick_reference = str(record.get("Quick Reference") or record.get("Hook") or "").strip()
        return {
            "overview": PanelPayload(
                panel_id="overview",
                title=f"Overview · {scenario.title}",
                content_blocks=(scenario.summary or "No summary available.",),
            ),
            "entities": PanelPayload(
                panel_id="entities",
                title="Entities",
                content_blocks=entities or ("No entities linked.",),
            ),
            "notes": PanelPayload(
                panel_id="notes",
                title="GM Notes",
                content_blocks=(notes or "No notes yet.",),
            ),
            "timeline": PanelPayload(
                panel_id="timeline",
                title="Timeline",
                content_blocks=(timeline or "No timeline steps.",),
            ),
            "quick_reference": PanelPayload(
                panel_id="quick_reference",
                title="Quick Reference",
                content_blocks=(quick_reference or "No quick reference entries.",),
            ),
        }

    def _format_entities(self, record: dict) -> tuple[str, ...]:
        """Flatten known entity fields into readable blocks."""
        blocks: list[str] = []
        for key in ("NPCs", "Places", "Objects", "Factions", "Clues"):
            value = record.get(key)
            if not value:
                continue
            if isinstance(value, list):
                items = ", ".join(str(item) for item in value if str(item).strip())
                if items:
                    blocks.append(f"{key}: {items}")
            elif isinstance(value, str) and value.strip():
                blocks.append(f"{key}: {value.strip()}")
        return tuple(blocks)
