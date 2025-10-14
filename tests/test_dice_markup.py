from dataclasses import dataclass, replace

import pytest

from modules.helpers.dice_markup import invalidate_action_pattern_cache, parse_inline_actions
from modules.maps.exporters.maptools import build_token_macros
from modules.helpers.system_config import AnalyzerPattern, SystemConfig
from modules.helpers import dice_markup
from modules.dice import dice_preferences


@dataclass(frozen=True)
class _SystemCase:
    slug: str
    base_roll: str
    config: SystemConfig


_SYSTEM_CASES = (
    _SystemCase(
        slug="d20",
        base_roll="1d20",
        config=SystemConfig(
            slug="d20",
            label="D20 System",
            default_formula="1d20",
            supported_faces=(4, 6, 8, 10, 12, 20),
            analyzer_patterns=tuple(),
            analyzer_config={
                "attack_roll": {"base": "1d20", "template": "{base}{bonus}"},
                "difficulty_buttons": (
                    {
                        "label": "Standard Challenge",
                        "template": "{attack_roll}",
                        "descriptor": "Standard",
                    },
                ),
            },
        ),
    ),
    _SystemCase(
        slug="2d20",
        base_roll="2d20",
        config=SystemConfig(
            slug="2d20",
            label="2d20 System",
            default_formula="2d20",
            supported_faces=(4, 6, 8, 10, 12, 20),
            analyzer_patterns=(
                AnalyzerPattern(
                    name="2d20_stat_block",
                    pattern=(
                        r"(?P<label>[A-Za-zÀ-ÖØ-öø-ÿ'’()\-/ ]+)\s+"
                        r"(?P<attack>[+-]\d+)\s+DM\s+"
                        r"(?P<damage>\d+d\d+(?:[+-]\d+)?)\s*"
                        r"\(TN\s*(?P<tn>\d+)\)"
                    ),
                    description="2d20 inline stat block",
                    metadata={
                        "difficulties": (
                            {
                                "group": "tn",
                                "label": "Target Number",
                                "template": "{attack_roll}",
                                "descriptor": "TN",
                                "notes_group": "tn",
                            },
                        ),
                    },
                ),
                AnalyzerPattern(
                    name="fallback",
                    pattern=(
                        r"(?P<label>[A-Za-zÀ-ÖØ-öø-ÿ'’()\-/ ]{2,}?)\s+"
                        r"(?P<attack>[+-]\d{1,3})\s+DM\s+"
                        r"(?P<damage>[^\s,;:.]+(?:\s+[a-zà-öø-ÿ'’\-/]+)*)"
                        r"(?!\s*\()"
                    ),
                    metadata={"ignore_case": False},
                ),
            ),
            analyzer_config={
                "attack_roll": {"base": "2d20", "template": "{base}{bonus}"},
                "difficulty_buttons": (
                    {
                        "label": "Standard Challenge",
                        "template": "{attack_roll}",
                        "descriptor": "Standard",
                    },
                ),
            },
        ),
    ),
)


@pytest.fixture(params=_SYSTEM_CASES, ids=lambda case: case.slug)
def system_case(monkeypatch, request):
    case: _SystemCase = request.param

    def _get_config():
        return case.config

    invalidate_action_pattern_cache()
    monkeypatch.setattr(dice_markup.system_config_helper, "get_current_system_config", _get_config)
    monkeypatch.setattr(dice_preferences.system_config, "get_current_system_config", _get_config)
    def _make_attack_roll(bonus):
        text = str(bonus or "").strip()
        if not text:
            return case.base_roll
        return _expected_roll(case, text)

    monkeypatch.setattr(dice_preferences, "make_attack_roll_formula", _make_attack_roll)
    yield case
    invalidate_action_pattern_cache()


def _expected_roll(case: _SystemCase, bonus: str) -> str:
    normalized = bonus.strip()
    if not normalized.startswith(("+", "-")):
        normalized = f"+{normalized}"
    return f"{case.base_roll}{normalized}"


def test_parse_inline_actions_basic_attack_and_damage(system_case: _SystemCase):
    text = "Attacks: [Strike +7|1d8+4 piercing]"
    display, actions, errors = parse_inline_actions(text)

    expected_display = "Attacks: Strike • Attack +7 • Damage 1d8+4 piercing"
    assert display == expected_display
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Strike"
    assert action["attack_bonus"] == "+7"
    assert action["attack_roll_formula"] == _expected_roll(system_case, "+7")
    assert action["damage_formula"] == "1d8+4"
    assert action["notes"] == "piercing"
    assert action["range"] == (9, 35)
    assert action["display_text"] == "Strike • Attack +7 • Damage 1d8+4 piercing"
    assert action["attack_span"] == (18, 27)
    assert action["damage_span"] == (30, 51)


def test_parse_inline_actions_multiple_segments(system_case: _SystemCase):
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


def test_parse_inline_actions_ignores_non_combat_segments(system_case: _SystemCase):
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


def test_parse_inline_actions_reports_errors_and_retains_markup(system_case: _SystemCase):
    text = "Broken [Strike +7|bad] text"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Broken [Strike +7|bad] text"
    assert actions == []
    assert len(errors) == 1
    error = errors[0]
    assert error["message"].startswith("Invalid damage formula")
    assert error["range"] == (7, 22)


def test_parse_inline_actions_handles_unclosed_segment(system_case: _SystemCase):
    text = "Broken [Strike +7|1d8"
    display, actions, errors = parse_inline_actions(text)

    assert display.endswith("[Strike +7|1d8")
    assert actions == []
    assert len(errors) == 1
    assert errors[0]["message"] == "Unclosed dice markup segment."


def test_parse_inline_actions_rejects_nested_segments(system_case: _SystemCase):
    text = "Nested [[Strike +7|1d8+4]]"
    display, actions, errors = parse_inline_actions(text)

    assert "[[Strike +7|1d8+4]]" in display
    assert actions == []
    assert len(errors) == 1
    assert "Nested '['" in errors[0]["message"]


def test_parse_inline_actions_defaults_label_when_missing(system_case: _SystemCase):
    text = "[+7|1d6]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Action • Attack +7 • Damage 1d6"
    assert errors == []
    assert len(actions) == 1
    assert actions[0]["label"] == "Action"
    assert actions[0]["attack_bonus"] == "+7"
    assert actions[0]["damage_formula"] == "1d6"


def test_parse_inline_actions_interprets_damage_plus_modifier_as_system_default(system_case: _SystemCase):
    text = "[Smite +8|+6 radiant]"
    display, actions, errors = parse_inline_actions(text)

    expected_damage = _expected_roll(system_case, "+6")
    assert display == f"Smite • Attack +8 • Damage {expected_damage} radiant"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["damage_formula"] == expected_damage
    assert action["notes"] == "radiant"


def test_parse_inline_actions_supports_dm_separator(system_case: _SystemCase):
    text = "[Strike +5 DM 1d8+3 slashing]"
    display, actions, errors = parse_inline_actions(text)

    assert display == "Strike • Attack +5 • Damage 1d8+3 slashing"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Strike"
    assert action["attack_bonus"] == "+5"
    assert action["attack_roll_formula"] == _expected_roll(system_case, "+5")
    assert action["damage_formula"] == "1d8+3"
    assert action["notes"] == "slashing"


def test_parse_inline_actions_supports_dm_with_modifier_damage(system_case: _SystemCase):
    text = "[Bash +4 DM +6 bludgeoning]"
    display, actions, errors = parse_inline_actions(text)

    expected_damage = _expected_roll(system_case, "+6")
    assert display == f"Bash • Attack +4 • Damage {expected_damage} bludgeoning"
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["label"] == "Bash"
    assert action["attack_bonus"] == "+4"
    assert action["attack_roll_formula"] == _expected_roll(system_case, "+4")
    assert action["damage_formula"] == expected_damage
    assert action["notes"] == "bludgeoning"


def test_parse_inline_actions_infers_unmarked_dm_segments(system_case: _SystemCase):
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
    assert claws["attack_roll_formula"] == _expected_roll(system_case, "+8")
    assert claws["damage_formula"] == "2d6+6"
    assert claws["notes"] is None
    assert claws["display_text"] == "Serres et bec • Attack +8 • Damage 2d6+6"

    assert sword["label"] == "Epée"
    assert sword["attack_bonus"] == "+2"
    assert sword["attack_roll_formula"] == _expected_roll(system_case, "+2")
    assert sword["damage_formula"] == "1d8+1"
    assert sword["notes"] is None
    assert sword["display_text"] == "Epée • Attack +2 • Damage 1d8+1"


def test_parse_inline_actions_pattern_difficulties_for_2d20(system_case: _SystemCase, monkeypatch: pytest.MonkeyPatch):
    if system_case.slug != "2d20":
        pytest.skip("Pattern-specific checks only apply to the 2d20 configuration")

    focused_config = replace(
        system_case.config,
        analyzer_patterns=system_case.config.analyzer_patterns[:1],
    )
    invalidate_action_pattern_cache()
    monkeypatch.setattr(dice_markup.system_config_helper, "get_current_system_config", lambda: focused_config)
    monkeypatch.setattr(dice_preferences.system_config, "get_current_system_config", lambda: focused_config)

    text = "Strike +7 DM 2d6+3 (TN 14)"
    display, actions, errors = parse_inline_actions(text)

    assert display == text
    assert errors == []
    assert len(actions) == 1

    action = actions[0]
    assert action["attack_roll_formula"] == _expected_roll(system_case, "+7")
    difficulties = action["difficulties"]
    assert len(difficulties) == 2

    pattern_button = next(item for item in difficulties if item["label"] == "Target Number")
    expected_pattern_formula = dice_preferences.canonicalize_formula(_expected_roll(system_case, "+7")) or _expected_roll(system_case, "+7")
    normalized_formula = pattern_button["formula"].replace(" ", "")
    assert normalized_formula == expected_pattern_formula.replace(" ", "")
    assert pattern_button["descriptor"] == "TN"
    assert pattern_button.get("notes") == "14"

    default_button = next(item for item in difficulties if item["label"] == "Standard Challenge")
    default_expected = dice_preferences.canonicalize_formula(_expected_roll(system_case, "+7")) or _expected_roll(system_case, "+7")
    default_normalized = default_button["formula"].replace(" ", "")
    assert default_normalized == default_expected.replace(" ", "")


def test_build_token_macros_uses_parsed_actions(system_case: _SystemCase):
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
    attack_command = macros[0]["commands"].splitlines()[0]
    expected_attack = dice_preferences.canonicalize_formula("1d20+7") or "1d20+7"
    assert attack_command.replace(" ", "") == f"/r{expected_attack.replace(' ', '')}[Attack]"
    assert "// Notes: slashing" in macros[0]["commands"]
    assert macros[1]["label"] == "Bite"
    damage_command = macros[1]["commands"].strip()
    expected_damage = dice_preferences.canonicalize_formula("1d6+2") or "1d6+2"
    assert damage_command.replace(" ", "") == f"/r{expected_damage.replace(' ', '')}[Damage]"
