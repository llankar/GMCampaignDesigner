"""SQLite persistence for character creation drafts in current campaign DB."""

from __future__ import annotations

import json

from db.db import get_connection


class CharacterDraftRepository:
    TABLE_NAME = "character_creation_drafts"

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    name TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def list_names(self) -> list[str]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT name FROM {self.TABLE_NAME} ORDER BY name COLLATE NOCASE")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def save(self, name: str, payload: dict) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO {self.TABLE_NAME} (name, payload_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

    def load(self, name: str) -> dict | None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT payload_json FROM {self.TABLE_NAME} WHERE name = ?", (name,))
            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row[0])
        finally:
            conn.close()
