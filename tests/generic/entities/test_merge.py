"""Tests for generic entity merge utilities."""

from modules.generic.entities.merge import merge_selected_entities


_TEMPLATE = {
    "fields": [
        {"name": "Name", "type": "text"},
        {"name": "Role", "type": "text"},
        {"name": "Description", "type": "longtext"},
        {"name": "Portrait", "type": "text"},
    ]
}


def test_merge_preserves_first_entity_name():
    items = [
        {"Name": "Alpha", "Role": "Scout"},
        {"Name": "Beta", "Role": "Guide"},
    ]

    result = merge_selected_entities(items, items, _TEMPLATE, "Name")

    assert result.survivor["Name"] == "Alpha"


def test_merge_text_fields_concatenate_in_selection_order():
    items = [
        {"Name": "Alpha", "Role": "Scout", "Description": "First line"},
        {"Name": "Beta", "Role": "Guide", "Description": "Second line"},
        {"Name": "Gamma", "Role": "Keeper", "Description": "Third line"},
    ]

    result = merge_selected_entities(items, items, _TEMPLATE, "Name")

    assert result.survivor["Role"] == "Scout Guide Keeper"
    assert result.survivor["Description"] == "First line\nSecond line\nThird line"


def test_merge_portraits_are_deduplicated_by_path_identity():
    items = [
        {"Name": "Alpha", "Portrait": "assets/portraits/a.png\nassets/portraits/b.png"},
        {"Name": "Beta", "Portrait": ["assets\\portraits\\a.png", "assets/portraits/c.png"]},
    ]

    result = merge_selected_entities(items, items, _TEMPLATE, "Name")

    assert result.survivor["Portrait"].splitlines() == [
        "assets/portraits/a.png",
        "assets/portraits/b.png",
        "assets/portraits/c.png",
    ]


def test_merge_removes_non_surviving_entities():
    alpha = {"Name": "Alpha", "Role": "Scout"}
    beta = {"Name": "Beta", "Role": "Guide"}
    untouched = {"Name": "Untouched", "Role": "Witness"}
    items = [alpha, beta, untouched]

    result = merge_selected_entities(items, [alpha, beta], _TEMPLATE, "Name")

    assert [item["Name"] for item in result.items] == ["Alpha", "Untouched"]
    assert result.removed == [beta]
