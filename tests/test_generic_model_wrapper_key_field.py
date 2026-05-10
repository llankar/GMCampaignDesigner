"""Regression tests for generic model wrapper key field."""

import sqlite3

from db.db import load_schema_from_json
from modules.generic.generic_model_wrapper import GenericModelWrapper


def _create_table_from_template(db_path, entity_slug):
    """Create table from template."""
    schema = load_schema_from_json(entity_slug)
    cols = ", ".join(f"{name} {kind}" for name, kind in schema)
    pk = schema[0][0]
    conn = sqlite3.connect(db_path)
    try:
        # Keep table from template resilient if this step fails.
        conn.execute(f"CREATE TABLE {entity_slug} ({cols}, PRIMARY KEY({pk}))")
        conn.commit()
    finally:
        conn.close()


def test_scenarios_save_items_uses_title_as_unique_field(tmp_path):
    """Verify that scenarios save items uses title as unique field."""
    db_path = tmp_path / "scenarios.db"
    _create_table_from_template(str(db_path), "scenarios")
    wrapper = GenericModelWrapper("scenarios", db_path=str(db_path))

    wrapper.save_items(
        [
            {"Title": "Scenario One", "Summary": "First"},
            {"Title": "Scenario Two", "Summary": "Second"},
        ]
    )

    wrapper.save_items([{"Title": "Scenario One", "Summary": "Updated"}], replace=True)

    loaded = wrapper.load_items()
    assert len(loaded) == 1
    assert loaded[0]["Title"] == "Scenario One"
    assert loaded[0]["Summary"] == "Updated"


def test_load_items_keeps_malformed_json_like_text(tmp_path):
    """Verify JSON-looking plain text does not break generic loading."""
    db_path = tmp_path / "calendar.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE events (Name TEXT PRIMARY KEY, Notes TEXT, Tags TEXT)"
        )
        conn.execute(
            "INSERT INTO events (Name, Notes, Tags) VALUES (?, ?, ?)",
            ("Session", "[draft note", '["one", "two"]'),
        )
        conn.commit()
    finally:
        conn.close()

    wrapper = GenericModelWrapper("events", db_path=str(db_path))

    loaded = wrapper.load_items()

    assert loaded == [
        {"Name": "Session", "Notes": "[draft note", "Tags": ["one", "two"]}
    ]


def test_load_items_keeps_json_decoder_stop_iteration_as_text(tmp_path, monkeypatch):
    """Verify odd decoder failures keep JSON-looking text loadable."""
    from modules.generic.deserialization import json_value_parser

    def broken_loads(_value):
        raise StopIteration(1)

    db_path = tmp_path / "calendar.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE events (Name TEXT PRIMARY KEY, Notes TEXT)")
        conn.execute(
            "INSERT INTO events (Name, Notes) VALUES (?, ?)",
            ("Session", "[draft note]"),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(json_value_parser.json, "loads", broken_loads)

    wrapper = GenericModelWrapper("events", db_path=str(db_path))

    assert wrapper.load_items() == [{"Name": "Session", "Notes": "[draft note]"}]


def test_deserialize_possible_json_keeps_direct_malformed_json_text():
    """Verify direct parser calls preserve malformed JSON-looking notes."""
    from modules.generic.deserialization.json_value_parser import deserialize_possible_json

    assert deserialize_possible_json(" [calendar note") == " [calendar note"
    assert deserialize_possible_json("{not really json") == "{not really json"


def test_incomplete_json_like_text_is_not_sent_to_decoder(monkeypatch):
    """Verify incomplete note text is kept without invoking JSON decoding."""
    from modules.generic.deserialization import json_value_parser

    def fail_if_called(_value):
        raise AssertionError("json.loads should not be called for incomplete text")

    monkeypatch.setattr(json_value_parser.json, "loads", fail_if_called)

    assert (
        json_value_parser.deserialize_possible_json("[calendar note")
        == "[calendar note"
    )
    assert (
        json_value_parser.deserialize_possible_json(" {calendar note")
        == " {calendar note"
    )


def test_complete_invalid_json_like_text_still_loads_as_plain_text():
    """Verify invalid-but-balanced note text remains plain text."""
    from modules.generic.deserialization.json_value_parser import deserialize_possible_json

    assert deserialize_possible_json("[calendar note]") == "[calendar note]"
    assert deserialize_possible_json("{not really json}") == "{not really json}"
