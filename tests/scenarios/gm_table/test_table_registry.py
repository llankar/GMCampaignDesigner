"""Tests for stable GM Table registry metadata."""

from modules.scenarios.gm_table.table_registry import (
    DEFAULT_GM_TABLE_ID,
    DEFAULT_GM_TABLE_NAMES,
    GM_TABLES,
    get_table_name,
    normalize_table_id,
)


def test_default_table_registry_exposes_six_stable_ids() -> None:
    """GM Table windows should be keyed by table_1 through table_6."""
    assert DEFAULT_GM_TABLE_ID == "table_1"
    assert DEFAULT_GM_TABLE_NAMES == ("Main", "Table2", "Table3", "Table4", "Table5", "Table6")
    assert [table.table_id for table in GM_TABLES] == [
        "table_1",
        "table_2",
        "table_3",
        "table_4",
        "table_5",
        "table_6",
    ]
    assert [table.name for table in GM_TABLES] == list(DEFAULT_GM_TABLE_NAMES)
    assert get_table_name("table_1") == "Main"
    assert get_table_name("table_6") == "Table6"


def test_normalize_table_id_falls_back_to_primary_table() -> None:
    """Unknown table ids should resolve to the default table."""
    assert normalize_table_id("table_2") == "table_2"
    assert normalize_table_id(" unknown ") == DEFAULT_GM_TABLE_ID
    assert normalize_table_id(None) == DEFAULT_GM_TABLE_ID
