"""Service adapters used by GM Screen 2 only."""

from __future__ import annotations

from modules.scenarios.gm_screen2.domain.models import ScenarioFilter, ScenarioSummary
from modules.scenarios.gm_screen2.services.interfaces import PanelPayloadProvider, ScenarioRepository
from modules.scenarios.gm_screen2.services.mappers.scenario_mapper import ScenarioRecordMapper


class GenericModelScenarioRepository(ScenarioRepository):
    """Scenario repository backed by GenericModelWrapper records."""

    def __init__(self, scenario_wrapper, mapper: ScenarioRecordMapper | None = None) -> None:
        self._scenario_wrapper = scenario_wrapper
        self._mapper = mapper or ScenarioRecordMapper()
        self._record_index: dict[str, dict] = {}

    def list_scenarios(self, filters: ScenarioFilter | None = None) -> list[ScenarioSummary]:
        """Load and optionally filter scenarios."""
        filters = filters or ScenarioFilter()
        records = self._scenario_wrapper.load_items()
        self._record_index.clear()
        summaries: list[ScenarioSummary] = []
        query = filters.query.lower().strip()

        for record in records:
            summary = self._mapper.to_summary(record)
            if query and query not in summary.title.lower() and query not in summary.summary.lower():
                continue
            if filters.tags and not set(filters.tags).intersection(summary.tags):
                continue
            self._record_index[summary.scenario_id] = record
            summaries.append(summary)

        return summaries

    def get_scenario(self, scenario_id: str) -> ScenarioSummary | None:
        """Load a single scenario summary from index or fallback scan."""
        if scenario_id in self._record_index:
            return self._mapper.to_summary(self._record_index[scenario_id])
        for record in self._scenario_wrapper.load_items():
            summary = self._mapper.to_summary(record)
            if summary.scenario_id == scenario_id:
                self._record_index[scenario_id] = record
                return summary
        return None

    def get_raw_record(self, scenario_id: str) -> dict | None:
        """Return raw persistence record for compatibility payload builders."""
        if scenario_id in self._record_index:
            return self._record_index[scenario_id]
        _ = self.get_scenario(scenario_id)
        return self._record_index.get(scenario_id)


class ScenarioPanelPayloadProvider(PanelPayloadProvider):
    """Panel payload provider mapped from repository records."""

    def __init__(self, repository: GenericModelScenarioRepository, mapper: ScenarioRecordMapper | None = None) -> None:
        self._repository = repository
        self._mapper = mapper or ScenarioRecordMapper()

    def load_panel_payloads(self, scenario: ScenarioSummary):
        """Build payloads from the scenario record."""
        raw_record = self._repository.get_raw_record(scenario.scenario_id) or {}
        return self._mapper.to_panel_payloads(raw_record, scenario)
