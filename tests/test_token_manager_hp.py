import json

import pytest

pytest.importorskip("PIL", reason="Pillow is required for token manager helpers")

from modules.maps.services import token_manager


def _make_record(stats=None, traits=None):
    record = {}
    if stats is not None:
        record["Stats"] = stats
    if traits is not None:
        record["Traits"] = traits
    return record


@pytest.mark.parametrize(
    "entity_type,record,expected",
    [
        (
            "Creature",
            _make_record(stats={"text": "HP: 15\nAC 12"}),
            15,
        ),
        (
            "PC",
            _make_record(stats="HP 5d8 + 4 (20)"),
            20,
        ),
        (
            "NPC",
            _make_record(traits={"text": "Speed 30\nHP 12"}),
            12,
        ),
        (
            "Creature",
            _make_record(traits="PV: 22"),
            22,
        ),
    ],
)
def test_extract_entity_hp_value(entity_type, record, expected):
    assert token_manager._extract_entity_hp_value(entity_type, record) == expected


def test_extract_entity_hp_value_from_serialized_json():
    stats = json.dumps({"text": "HP 40 (10d8 + 5)"})
    record = _make_record(stats=stats)
    assert token_manager._extract_entity_hp_value("Creature", record) == 40


def test_extract_entity_hp_value_missing_hp():
    record = _make_record(stats="Speed 30 ft")
    assert token_manager._extract_entity_hp_value("Creature", record) is None
