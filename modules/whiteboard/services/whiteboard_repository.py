import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from db.db import get_connection
from modules.helpers.logging_helper import log_module_import, log_warning
from modules.whiteboard.services.whiteboard_storage import WhiteboardState

log_module_import(__name__)

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _now_iso() -> str:
    return datetime.utcnow().strftime(_TIMESTAMP_FMT)


@dataclass
class WhiteboardSnapshot:
    snapshot_id: int
    scenario_title: str
    saved_at: str


class WhiteboardRepository:
    """Persist and fetch whiteboard states from the campaign database."""

    _TABLE = "whiteboard_states"

    def __init__(self) -> None:
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self._TABLE}_scenario_saved_at ON {self._TABLE} (scenario_title, saved_at DESC)"
            )
            conn.commit()
        except Exception:
            log_warning("Unable to ensure whiteboard table", func_name="WhiteboardRepository._ensure_table")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def save_snapshot(self, scenario_title: str, state: WhiteboardState) -> Tuple[int, str]:
        title = scenario_title or "Unassigned"
        saved_at = _now_iso()
        payload = json.dumps(state.to_dict(), ensure_ascii=False)
        conn = get_connection()
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO {self._TABLE} (scenario_title, payload_json, saved_at) VALUES (?, ?, ?)",
                (title, payload, saved_at),
            )
            conn.commit()
            return int(cursor.lastrowid), saved_at
        finally:
            conn.close()

    def load_latest_state(self, scenario_title: str) -> Tuple[Optional[WhiteboardState], Optional[str]]:
        title = scenario_title or "Unassigned"
        conn = get_connection()
        conn.row_factory = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT payload_json, saved_at
                FROM {self._TABLE}
                WHERE scenario_title = ?
                ORDER BY saved_at DESC, id DESC
                LIMIT 1
                """,
                (title,),
            )
            row = cursor.fetchone()
            if not row:
                return None, None
            payload_json, saved_at = row
            try:
                data = json.loads(payload_json)
            except json.JSONDecodeError:
                return None, None
            return WhiteboardState.from_dict(data), saved_at
        finally:
            conn.close()

    def list_history(self, scenario_title: str, limit: int = 15) -> List[WhiteboardSnapshot]:
        title = scenario_title or "Unassigned"
        conn = get_connection()
        conn.row_factory = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT id, saved_at
                FROM {self._TABLE}
                WHERE scenario_title = ?
                ORDER BY saved_at DESC, id DESC
                LIMIT ?
                """,
                (title, limit),
            )
            rows = cursor.fetchall() or []
            return [WhiteboardSnapshot(snapshot_id=int(r[0]), scenario_title=title, saved_at=str(r[1])) for r in rows]
        finally:
            conn.close()

    def load_snapshot(self, snapshot_id: int) -> Optional[WhiteboardState]:
        conn = get_connection()
        conn.row_factory = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT payload_json FROM {self._TABLE} WHERE id = ?",
                (snapshot_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            try:
                data = json.loads(row[0])
            except json.JSONDecodeError:
                return None
            return WhiteboardState.from_dict(data)
        finally:
            conn.close()
