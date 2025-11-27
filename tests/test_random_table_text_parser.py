"""Tests for the permissive random table text parser."""

import pytest

from modules.scenarios.importers.random_table_text_parser import (
    RandomTableImportError,
    parse_random_table_text,
)


def test_accepts_common_range_patterns():
    raw_text = """
    1-2 Light rain begins
    03–04: Thunder cracks overhead
    5-5- This dash is part of the text
    """

    entries = parse_random_table_text(raw_text)

    assert entries == [
        {"min": 1, "max": 2, "result": "Light - rain begins", "tags": []},
        {"min": 3, "max": 4, "result": "Thunder - cracks overhead", "tags": []},
        {"min": 5, "max": 5, "result": "This - dash is part of the text", "tags": []},
    ]


def test_accepts_single_values_with_varied_separators():
    raw_text = """
    7 Quiet street
    8. Crowd gathers
    9) Market closes early
    """

    entries = parse_random_table_text(raw_text)

    assert [entry["min"] for entry in entries] == [7, 8, 9]
    assert [entry["max"] for entry in entries] == [7, 8, 9]
    assert [entry["result"] for entry in entries] == [
        "Quiet - street",
        "Crowd - gathers",
        "Market - closes early",
    ]


def test_rejects_invalid_lines():
    with pytest.raises(RandomTableImportError):
        parse_random_table_text("not a valid entry")

