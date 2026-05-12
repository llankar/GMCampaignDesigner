"""Lightweight data access for the campaign overview dashboard."""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Sequence

from db.db import get_connection
from modules.campaigns.shared.arc_parser import coerce_arc_list
from modules.campaigns.ui.graphical_display.data import iter_scenario_link_fields
from modules.generic.json_value_deserializer import deserialize_possible_json

CAMPAIGN_OVERVIEW_COLUMNS: tuple[str, ...] = (
    "Name",
    "Logline",
    "Genre",
    "Tone",
    "Status",
    "Setting",
    "MainObjective",
    "Stakes",
    "Themes",
    "LinkedScenarios",
    "Arcs",
)

CAMPAIGN_CONFIG_COLUMNS: tuple[str, ...] = (
    "overview_selected_arc",
    "overview_selected_scenario",
)

SCENARIO_OVERVIEW_COLUMNS: tuple[str, ...] = (
    "Title",
    "Summary",
    "Briefing",
    "ScenarioBriefing",
    "GMBriefing",
    "SessionBriefing",
    "Brief",
    "Objective",
    "Objectives",
    "Goal",
    "Goals",
    "CurrentObjective",
    "MainObjective",
    "DesiredOutcome",
    "Hook",
    "Hooks",
    "PlotHook",
    "PlotHooks",
    "IntroHook",
    "IncitingIncident",
    "SceneSummary",
    "Stakes",
    "Consequences",
    "Outcome",
    "FailureState",
    "Threat",
    "Threats",
    "Scenes",
    "Secrets",
)


class CampaignOverviewRepository:
    """Load only the columns required by the graphical campaign overview."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the repository with an optional database override."""
        self._db_path = db_path

    def list_campaigns_for_overview(self) -> list[dict[str, Any]]:
        """Return campaign rows with only overview fields and saved focus metadata."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                campaign_columns = self._existing_columns(conn, "campaigns", CAMPAIGN_OVERVIEW_COLUMNS)
                if "Name" not in campaign_columns:
                    return []

                config_columns = self._existing_columns(conn, "campaign_config", CAMPAIGN_CONFIG_COLUMNS)
                select_expressions = [f'c.{_quote_identifier(column)}' for column in campaign_columns]
                join_clause = ""
                if config_columns:
                    select_expressions.extend(
                        f'cfg.{_quote_identifier(column)} AS {_quote_identifier(column)}'
                        for column in config_columns
                    )
                    join_clause = "LEFT JOIN campaign_config cfg ON cfg.campaign_name = c.Name"

                cursor = conn.execute(
                    f"""
                    SELECT {', '.join(select_expressions)}
                    FROM campaigns c
                    {join_clause}
                    ORDER BY c.Name COLLATE NOCASE
                    """
                )
                return [_deserialize_row(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def load_scenarios_for_campaign(self, campaign: dict[str, Any] | None) -> list[dict[str, Any]]:
        """Return only scenarios referenced by the selected campaign overview data."""
        scenario_titles = self._linked_scenario_titles(campaign)
        if not scenario_titles:
            return []

        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                scenario_columns = self._scenario_columns(conn)
                if "Title" not in scenario_columns:
                    return []

                placeholders = ", ".join("?" for _ in scenario_titles)
                cursor = conn.execute(
                    f"""
                    SELECT {', '.join(_quote_identifier(column) for column in scenario_columns)}
                    FROM scenarios
                    WHERE Title IN ({placeholders})
                    """,
                    scenario_titles,
                )
                rows_by_title = {
                    str(item.get("Title") or "").strip(): item
                    for item in (_deserialize_row(row) for row in cursor.fetchall())
                }
                return [rows_by_title[title] for title in scenario_titles if title in rows_by_title]
        except sqlite3.Error:
            return []

    def list_campaigns(self) -> list[dict[str, Any]]:
        """Backward-compatible alias for overview campaign listing."""
        return self.list_campaigns_for_overview()

    def list_linked_scenarios(self, campaign: dict[str, Any] | None) -> list[dict[str, Any]]:
        """Backward-compatible alias for selected-campaign scenario loading."""
        return self.load_scenarios_for_campaign(campaign)

    def _connect(self) -> sqlite3.Connection:
        if self._db_path:
            return sqlite3.connect(self._db_path)
        return get_connection()

    def _scenario_columns(self, conn: sqlite3.Connection) -> list[str]:
        link_columns = tuple(field_name for _linked_type, field_name in iter_scenario_link_fields())
        return self._existing_columns(conn, "scenarios", (*SCENARIO_OVERVIEW_COLUMNS, *link_columns))

    @staticmethod
    def _existing_columns(conn: sqlite3.Connection, table: str, requested_columns: Sequence[str]) -> list[str]:
        cursor = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})")
        existing = {str(row[1]) for row in cursor.fetchall()}
        return [column for column in requested_columns if column in existing]

    @staticmethod
    def _linked_scenario_titles(campaign: dict[str, Any] | None) -> list[str]:
        if not isinstance(campaign, dict):
            return []

        titles: list[str] = []
        _extend_unique_titles(titles, _coerce_title_list(campaign.get("LinkedScenarios")))
        for arc in coerce_arc_list(campaign.get("Arcs")):
            _extend_unique_titles(titles, _coerce_title_list(arc.get("scenarios")))
        return titles


def _deserialize_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: deserialize_possible_json(row[key]) for key in row.keys()}


def _coerce_title_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [title for title in (str(item or "").strip() for item in value) if title]
    if isinstance(value, tuple):
        return [title for title in (str(item or "").strip() for item in value) if title]
    text = str(value or "").strip()
    return [text] if text else []


def _extend_unique_titles(target: list[str], titles: Iterable[str]) -> None:
    seen = set(target)
    for title in titles:
        if title in seen:
            continue
        target.append(title)
        seen.add(title)


def _quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'
