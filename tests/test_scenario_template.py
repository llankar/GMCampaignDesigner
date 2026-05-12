"""Regression tests for scenario template fields."""

from db.db import load_schema_from_json
from modules.helpers.template_loader import load_template


def test_scenario_template_exposes_status_after_title():
    """Verify that scenarios expose Status as a built-in field for UI columns."""
    field_names = [field["name"] for field in load_template("scenarios")["fields"]]

    assert field_names[:2] == ["Title", "Status"]


def test_scenario_schema_includes_status_column():
    """Verify that schema sync can add Status to existing campaign databases."""
    schema = dict(load_schema_from_json("scenarios"))

    assert schema["Status"] == "TEXT"
