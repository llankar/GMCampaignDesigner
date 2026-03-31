"""Repository helpers for campaign config."""

from __future__ import annotations

from db.db import get_connection

TABLE_NAME = "campaign_config"


class CampaignConfigRepository:
    """Database access layer for app-managed per-campaign configuration."""

    def load_overview_focus(self, campaign_name: str) -> tuple[str, str]:
        """Load overview focus."""
        normalized_name = str(campaign_name or "").strip()
        if not normalized_name:
            return "", ""

        with get_connection() as conn:
            # Keep this resource scoped to overview focus.
            cursor = conn.cursor()
            self._ensure_table(cursor)
            cursor.execute(
                f"""
                SELECT overview_selected_arc, overview_selected_scenario
                FROM {TABLE_NAME}
                WHERE campaign_name = ?
                """,
                (normalized_name,),
            )
            row = cursor.fetchone()
            if row is None:
                return "", ""
            return str(row[0] or "").strip(), str(row[1] or "").strip()

    def save_overview_focus(self, campaign_name: str, *, arc_name: str, scenario_title: str) -> None:
        """Save overview focus."""
        normalized_name = str(campaign_name or "").strip()
        if not normalized_name:
            return

        with get_connection() as conn:
            # Keep this resource scoped to overview focus.
            cursor = conn.cursor()
            self._ensure_table(cursor)
            cursor.execute(
                f"""
                INSERT INTO {TABLE_NAME} (
                    campaign_name,
                    overview_selected_arc,
                    overview_selected_scenario
                )
                VALUES (?, ?, ?)
                ON CONFLICT(campaign_name)
                DO UPDATE SET
                    overview_selected_arc = excluded.overview_selected_arc,
                    overview_selected_scenario = excluded.overview_selected_scenario
                """,
                (normalized_name, str(arc_name or "").strip(), str(scenario_title or "").strip()),
            )
            conn.commit()

    @staticmethod
    def _ensure_table(cursor) -> None:
        """Ensure table."""
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                campaign_name TEXT PRIMARY KEY,
                overview_selected_arc TEXT,
                overview_selected_scenario TEXT
            )
            """
        )
