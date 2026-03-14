import sqlite3

from db.db import load_schema_from_json
from modules.generic.generic_model_wrapper import GenericModelWrapper


def _create_table_from_template(db_path, entity_slug):
    schema = load_schema_from_json(entity_slug)
    cols = ", ".join(f"{name} {kind}" for name, kind in schema)
    pk = schema[0][0]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"CREATE TABLE {entity_slug} ({cols}, PRIMARY KEY({pk}))")
        conn.commit()
    finally:
        conn.close()


def test_scenarios_save_items_uses_title_as_unique_field(tmp_path):
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
