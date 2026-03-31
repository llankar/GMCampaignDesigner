"""Regression tests for arcs read only preview."""

import importlib.util
import sys
import types
from pathlib import Path


sys.modules.setdefault("customtkinter", types.SimpleNamespace(CTkFrame=object, CTkLabel=object, CTkTextbox=object))

MODULE_PATH = Path("modules/campaigns/ui/arcs_read_only_preview.py")
spec = importlib.util.spec_from_file_location("arcs_read_only_preview", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
ReadOnlyArcsPreview = module.ReadOnlyArcsPreview


def test_coerce_arcs_from_dict_wrapper_with_arcs_key():
    """Verify that coerce arcs from dict wrapper with arcs key."""
    raw = {
        "arcs": [
            {"name": "Arc Alpha", "status": "Running"},
            "ignore-me",
            {"name": "Arc Beta"},
        ]
    }

    arcs = ReadOnlyArcsPreview._coerce_to_arc_list(raw)

    assert arcs == [
        {"name": "Arc Alpha", "status": "Running"},
        {"name": "Arc Beta"},
    ]


def test_coerce_arcs_from_dict_wrapper_with_text_payload():
    """Verify that coerce arcs from dict wrapper with text payload."""
    raw = {
        "text": '[{"name": "Arc Through Text", "objective": "Find relic"}]'
    }

    arcs = ReadOnlyArcsPreview._coerce_to_arc_list(raw)

    assert arcs == [{"name": "Arc Through Text", "objective": "Find relic"}]


def test_coerce_arcs_from_stringified_dict_wrapper():
    """Verify that coerce arcs from stringified dict wrapper."""
    raw = '{"arcs": [{"name": "Nested Arc", "summary": "setup"}]}'

    arcs = ReadOnlyArcsPreview._coerce_to_arc_list(raw)

    assert arcs == [{"name": "Nested Arc", "summary": "setup"}]
