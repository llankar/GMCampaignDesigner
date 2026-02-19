from __future__ import annotations

import json
import sqlite3
from typing import List, Tuple

from db.db import get_connection
from modules.helpers.logging_helper import log_module_import
from modules.timer.models import TimerPreset, TimerState

log_module_import(__name__)


class TimerPersistence:
    """SQLite persistence for active timers and reusable presets."""

    def __init__(self) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = get_connection()
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_timers (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_timer_presets (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def load(self) -> Tuple[List[TimerState], List[TimerPreset]]:
        self._ensure_schema()
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT payload_json FROM campaign_timers")
            timers_rows = cursor.fetchall()
            timers: List[TimerState] = []
            for row in timers_rows:
                try:
                    payload = json.loads(row["payload_json"])
                    timers.append(TimerState.from_dict(payload))
                except Exception:
                    continue

            cursor.execute("SELECT payload_json FROM campaign_timer_presets")
            presets_rows = cursor.fetchall()
            presets: List[TimerPreset] = []
            for row in presets_rows:
                try:
                    payload = json.loads(row["payload_json"])
                    presets.append(TimerPreset.from_dict(payload))
                except Exception:
                    continue

            return timers, presets
        finally:
            conn.close()

    def save(self, timers: List[TimerState], presets: List[TimerPreset]) -> None:
        self._ensure_schema()
        conn = get_connection()
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.cursor()

            cursor.execute("DELETE FROM campaign_timers")
            cursor.executemany(
                "INSERT INTO campaign_timers (id, payload_json) VALUES (?, ?)",
                [(timer.id, json.dumps(timer.to_dict(), ensure_ascii=False)) for timer in timers],
            )

            cursor.execute("DELETE FROM campaign_timer_presets")
            cursor.executemany(
                "INSERT INTO campaign_timer_presets (id, payload_json) VALUES (?, ?)",
                [(preset.id, json.dumps(preset.to_dict(), ensure_ascii=False)) for preset in presets],
            )

            conn.commit()
        except Exception:
            # Timer persistence should not break UI interactions.
            pass
        finally:
            conn.close()
