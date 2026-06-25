"""Stable GM Table identifiers and default display names."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_GM_TABLE_NAMES = ("Main", "Table2", "Table3", "Table4", "Table5", "Table6")
DEFAULT_GM_TABLE_ID = "table_1"


@dataclass(frozen=True)
class GMTableRegistration:
    """A stable GM Table slot available in the application."""

    table_id: str
    name: str


GM_TABLES = tuple(
    GMTableRegistration(table_id=f"table_{index}", name=name)
    for index, name in enumerate(DEFAULT_GM_TABLE_NAMES, start=1)
)
GM_TABLE_IDS = frozenset(table.table_id for table in GM_TABLES)
_GM_TABLE_NAMES_BY_ID = {table.table_id: table.name for table in GM_TABLES}


def normalize_table_id(table_id: str | None = None) -> str:
    """Return a known GM Table id, falling back to the primary table."""
    candidate = str(table_id or DEFAULT_GM_TABLE_ID).strip()
    return candidate if candidate in GM_TABLE_IDS else DEFAULT_GM_TABLE_ID


def get_table_name(table_id: str) -> str:
    """Return the default display name for a stable table id."""
    return _GM_TABLE_NAMES_BY_ID[normalize_table_id(table_id)]
