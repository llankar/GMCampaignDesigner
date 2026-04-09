"""GM Screen 2-specific mapping from scenario records to domain models."""

from __future__ import annotations

from modules.scenarios.gm_screen2.domain.models import PanelItem, PanelPayload, PanelSection, ScenarioSummary


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
        """Build structured payloads for all desktop panel types."""
        notes = self._coerce_lines(record.get("Notes") or record.get("GM Notes"))
        timeline = self._coerce_lines(record.get("Timeline"))
        quick_reference = self._coerce_lines(record.get("Quick Reference") or record.get("Hook"))
        entities = self._entities_sections(record)

        return {
            "overview": PanelPayload(
                panel_id="overview",
                title=f"Overview · {scenario.title}",
                sections=(
                    PanelSection("Summary", (PanelItem(kind="text", text=(scenario.summary or "No summary available.")),)),
                    PanelSection("Tags", tuple(PanelItem(kind="chip", title=tag) for tag in scenario.tags) or (PanelItem(kind="text", text="No tags."),)),
                ),
            ),
            "entities": PanelPayload(
                panel_id="entities",
                title="Entities",
                sections=entities or (PanelSection("Entities", (PanelItem(kind="text", text="No entities linked."),)),),
            ),
            "notes": PanelPayload(
                panel_id="notes",
                title="GM Notes",
                sections=(PanelSection("Notes", tuple(PanelItem(kind="card", title=f"Note {idx + 1}", text=line) for idx, line in enumerate(notes)) or (PanelItem(kind="text", text="No notes yet."),)),),
            ),
            "timeline": PanelPayload(
                panel_id="timeline",
                title="Timeline",
                sections=(PanelSection("Steps", tuple(PanelItem(kind="card", title=f"Step {idx + 1}", text=line) for idx, line in enumerate(timeline)) or (PanelItem(kind="text", text="No timeline steps."),)),),
            ),
            "quick_reference": PanelPayload(
                panel_id="quick_reference",
                title="Quick Reference",
                sections=(PanelSection("Checklist", tuple(PanelItem(kind="text", text=line) for line in quick_reference) or (PanelItem(kind="text", text="No quick reference entries."),)),),
            ),
        }

    def _entities_sections(self, record: dict) -> tuple[PanelSection, ...]:
        sections: list[PanelSection] = []
        for key in ("NPCs", "Places", "Objects", "Factions", "Clues"):
            value = record.get(key)
            values = self._coerce_list(value)
            if values:
                sections.append(PanelSection(key, tuple(PanelItem(kind="chip", title=item) for item in values)))
        return tuple(sections)

    def _coerce_lines(self, value) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [self._clean_text(item) for item in value if self._clean_text(item)]
        text = self._clean_text(value)
        if not text:
            return []
        if "\n" in text:
            return [line.strip(" -•") for line in text.splitlines() if line.strip()]
        return [text]

    def _coerce_list(self, value) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [self._clean_text(item) for item in value if self._clean_text(item)]
        text = self._clean_text(value)
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    def _clean_text(self, value) -> str:
        if isinstance(value, dict):
            if "text" in value:
                return str(value.get("text") or "").strip()
            return " ".join(str(v).strip() for v in value.values() if str(v).strip())
        return str(value or "").strip()
