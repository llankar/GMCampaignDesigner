"""Regression tests for mojibake repair in text helpers."""

from modules.helpers.text_helpers import coerce_text, format_multiline_text


def test_coerce_text_repairs_common_mojibake_without_touching_clean_unicode():
    """Verify that coerce_text repairs common mojibake and preserves clean text."""
    clean_name = "Prot\u00e9ger un site PharmaCorp"
    single_encoded_name = clean_name.encode("utf-8").decode("cp1252")
    double_encoded_name = single_encoded_name.encode("utf-8").decode("cp1252")
    clean_logline = "Planned \u2022 9 scenarios"
    mojibake_logline = clean_logline.encode("utf-8").decode("cp1252")
    clean_title = "Arc I \u2014 Inciting Pressure"
    mojibake_title = clean_title.encode("utf-8").decode("cp1252")

    assert coerce_text(clean_name) == clean_name
    assert coerce_text(single_encoded_name) == clean_name
    assert coerce_text(double_encoded_name) == clean_name
    assert coerce_text(mojibake_logline) == clean_logline
    assert coerce_text(clean_title) == clean_title
    assert coerce_text(mojibake_title) == clean_title


def test_format_multiline_text_repairs_legacy_mojibake():
    """Verify that format_multiline_text keeps clean line breaks while repairing mojibake."""
    clean_value = "Premi\u00e8re ligne\nSeconde ligne \u2014 avec d\u00e9tail"
    mojibake_value = clean_value.encode("utf-8").decode("cp1252")

    assert format_multiline_text(clean_value) == clean_value
    assert format_multiline_text(mojibake_value) == clean_value
