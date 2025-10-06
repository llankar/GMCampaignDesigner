from modules.helpers.dice_markup import parse_inline_actions
from modules.maps.exporters.maptools import build_token_macros


def test_parse_inline_actions_basic_attack_and_damage():
    text = "Attacks: [Strike +7|1d8+4 piercing]"
    display, actions, errors = parse_inline_actions(text)

    expected_display = "Attacks: Strike • Attack +7 • Damage 1d8+4 piercing"
    assert display == expected_display
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Strike"
    assert action["attack_bonus"] == "+7"
    assert action["attack_roll_formula"] == "1d20+7"
    assert action["damage_formula"] == "1d8+4"
    assert action["notes"] == "piercing"
    assert action["range"] == (9, 35)
    assert action["display_text"] == "Strike • Attack +7 • Damage 1d8+4 piercing"
    assert action["attack_span"] == (18, 27)
    assert action["damage_span"] == (30, 51)


def test_parse_inline_actions_multiple_segments():
    text = "[Strike +7|1d8+4 slashing] and [Fireball|8d6 fire]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Strike • Attack +7 • Damage 1d8+4 slashing and Fireball • Damage 8d6 fire"
    assert errors == []
    assert len(actions) == 2

    strike, fireball = actions
    assert strike["label"] == "Strike"
    assert strike["attack_bonus"] == "+7"
    assert strike["damage_formula"] == "1d8+4"
    assert strike["notes"] == "slashing"
    assert strike["display_text"] == "Strike • Attack +7 • Damage 1d8+4 slashing"
    assert strike["attack_span"] == (9, 18)
    assert strike["damage_span"] == (21, 42)

    assert fireball["label"] == "Fireball"
    assert fireball["attack_bonus"] is None
    assert fireball["damage_formula"] == "8d6"
    assert fireball["notes"] == "fire"
    assert fireball["display_text"] == "Fireball • Damage 8d6 fire"
    assert fireball["attack_span"] is None
    assert fireball["damage_span"] == (58, 73)


def test_parse_inline_actions_ignores_non_combat_segments():
    text = """Lore [Some note]\n[Strike +6|1d8+3 slashing]\nFlavor [Another note]\n"""

    display, actions, errors = parse_inline_actions(text)

    assert "[Some note]" in display
    assert "[Another note]" in display
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Strike"
    assert action["attack_bonus"] == "+6"
    assert action["damage_formula"] == "1d8+3"


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

    assert display == "Action • Attack +7 • Damage 1d6"
    assert errors == []
    assert len(actions) == 1
    assert actions[0]["label"] == "Action"
    assert actions[0]["attack_bonus"] == "+7"
    assert actions[0]["damage_formula"] == "1d6"


def test_parse_inline_actions_interprets_damage_plus_modifier_as_d20():
    text = "[Smite +8|+6 radiant]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Smite • Attack +8 • Damage 1d20+6 radiant"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["damage_formula"] == "1d20+6"
    assert action["notes"] == "radiant"


def test_parse_inline_actions_supports_dm_separator():
    text = "[Strike +5 DM 1d8+3 slashing]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Strike • Attack +5 • Damage 1d8+3 slashing"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Strike"
    assert action["attack_bonus"] == "+5"
    assert action["attack_roll_formula"] == "1d20+5"
    assert action["damage_formula"] == "1d8+3"
    assert action["notes"] == "slashing"


def test_parse_inline_actions_supports_dm_with_modifier_damage():
    text = "[Bash +4 DM +6 bludgeoning]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Bash • Attack +4 • Damage 1d20+6 bludgeoning"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Bash"
    assert action["attack_bonus"] == "+4"
    assert action["attack_roll_formula"] == "1d20+4"
    assert action["damage_formula"] == "1d20+6"
    assert action["notes"] == "bludgeoning"


def test_parse_inline_actions_infers_unmarked_dm_segments():
    text = (
        "[Archétype standard] NC¥, créature humanoïde FOR +1 DEX +1 CON +1 INT +0 SAG +0 CHA -2 "
        "DEF 14 PV 9 Init 12 Serres et bec +8 DM 2d6+6 Epée +2 DM 1d8+1"
    )

    display, actions, errors = parse_inline_actions(text)

    assert display == text
    assert errors == []
    assert len(actions) == 2

    claws, sword = actions

    assert claws["label"] == "Serres et bec"
    assert claws["attack_bonus"] == "+8"
    assert claws["attack_roll_formula"] == "1d20+8"
    assert claws["damage_formula"] == "2d6+6"
    assert claws["notes"] is None
    assert claws["display_text"] == "Serres et bec • Attack +8 • Damage 2d6+6"

    assert sword["label"] == "Epée"
    assert sword["attack_bonus"] == "+2"
    assert sword["attack_roll_formula"] == "1d20+2"
    assert sword["damage_formula"] == "1d8+1"
    assert sword["notes"] is None
    assert sword["display_text"] == "Epée • Attack +2 • Damage 1d8+1"


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
