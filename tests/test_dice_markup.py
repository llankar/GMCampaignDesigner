from modules.helpers.dice_markup import parse_inline_actions
from modules.maps.exporters.maptools import build_token_macros


def test_parse_inline_actions_basic_attack_and_damage():
    text = "Attacks: [Strike +7|1d8+4 piercing]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Attacks: Strike (piercing)"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Strike"
    assert action["attack_bonus"] == "+7"
    assert action["attack_roll_formula"] == "1d20+7"
    assert action["damage_formula"] == "1d8+4"
    assert action["notes"] == "piercing"
    assert action["range"] == (9, 35)


def test_parse_inline_actions_multiple_segments():
    text = "[Strike +7|1d8+4 slashing] and [Fireball|8d6 fire]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Strike (slashing) and Fireball (fire)"
    assert errors == []
    assert len(actions) == 2

    strike, fireball = actions
    assert strike["label"] == "Strike"
    assert strike["attack_bonus"] == "+7"
    assert strike["damage_formula"] == "1d8+4"
    assert strike["notes"] == "slashing"

    assert fireball["label"] == "Fireball"
    assert fireball["attack_bonus"] is None
    assert fireball["damage_formula"] == "8d6"
    assert fireball["notes"] == "fire"


def test_parse_inline_actions_reports_errors_and_retains_markup():
    text = "Broken [Strike +7|bad] text"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Broken [Strike +7|bad] text"
    assert actions == []
    assert len(errors) == 1
    error = errors[0]
    assert error["message"].startswith("Invalid damage formula")
    assert error["range"] == (7, 22)


def test_parse_inline_actions_handles_unclosed_segment():
    text = "Broken [Strike +7|1d8"
    display, actions, errors = parse_inline_actions(text)

    assert display.endswith("[Strike +7|1d8")
    assert actions == []
    assert len(errors) == 1
    assert errors[0]["message"] == "Unclosed dice markup segment."


def test_parse_inline_actions_rejects_nested_segments():
    text = "Nested [[Strike +7|1d8+4]]"
    display, actions, errors = parse_inline_actions(text)

    assert "[[Strike +7|1d8+4]]" in display
    assert actions == []
    assert len(errors) == 1
    assert "Nested '['" in errors[0]["message"]


def test_parse_inline_actions_defaults_label_when_missing():
    text = "[+7|1d6]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Action"
    assert errors == []
    assert len(actions) == 1
    assert actions[0]["label"] == "Action"
    assert actions[0]["attack_bonus"] == "+7"
    assert actions[0]["damage_formula"] == "1d6"


def test_build_token_macros_uses_parsed_actions():
    actions = [
        {
            "label": "Strike",
            "attack_roll_formula": "1d20+7",
            "damage_formula": "1d8+4",
            "notes": "slashing",
        },
        {
            "label": "Bite",
            "damage_formula": "1d6+2",
        },
    ]

    macros = build_token_macros(actions, token_name="Wolf")

    assert len(macros) == 2
    assert macros[0]["label"] == "Strike"
    assert "/r 1d20+7 [Attack]" in macros[0]["commands"]
    assert "// Notes: slashing" in macros[0]["commands"]
    assert macros[1]["label"] == "Bite"
    assert macros[1]["commands"].strip().startswith("/r 1d6+2")
