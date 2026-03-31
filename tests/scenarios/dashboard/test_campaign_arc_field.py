"""Regression tests for campaign arc field."""

import importlib.util
import sys
import types
from pathlib import Path


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(CTkFrame=object, CTkLabel=object, CTkButton=object, CTkFont=object),
)

MODULE_PATH = Path("modules/scenarios/gm_screen/dashboard/widgets/campaign_arc_field.py")
spec = importlib.util.spec_from_file_location("campaign_arc_field", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
coerce_arc_list = module.coerce_arc_list


def test_coerce_arc_list_from_dict_with_arcs_key():
    """Verify that coerce arc list from dict with arcs key."""
    raw = {
        "arcs": [
            {"name": "Arc Alpha", "status": "Running"},
            "ignore-me",
            {"name": "Arc Beta"},
        ]
    }

    arcs = coerce_arc_list(raw)

    assert arcs == [
        {"name": "Arc Alpha", "status": "In Progress"},
        {"name": "Arc Beta", "status": "Planned"},
    ]


def test_coerce_arc_list_from_text_payload():
    """Verify that coerce arc list from text payload."""
    raw = {"text": '[{"name": "Text Arc", "objective": "Find clue"}]'}

    arcs = coerce_arc_list(raw)

    assert arcs == [{"name": "Text Arc", "objective": "Find clue", "status": "Planned"}]


def test_coerce_arc_list_single_arc_dict_normalizes_status():
    """Verify that coerce arc list single arc dict normalizes status."""
    arcs = coerce_arc_list({"name": "Arc Solo", "status": "done"})

    assert arcs == [{"name": "Arc Solo", "status": "Completed"}]
