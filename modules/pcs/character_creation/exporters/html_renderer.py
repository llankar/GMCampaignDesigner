"""HTML rendering for Savage Fate character sheets."""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

from ..progression import ADVANCEMENT_OPTIONS

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "character_sheet.html"


def _rule_attr(rules_result, key: str, default=""):
    if isinstance(rules_result, dict):
        return rules_result.get(key, default)
    return getattr(rules_result, key, default)


def _build_skill_rows(skill_dice: dict, favorites: set[str]) -> str:
    items = list(skill_dice.items())
    max_rows = max(15, len(items))
    rows: list[str] = []
    for idx in range(max_rows):
        if idx < len(items):
            skill, die = items[idx]
            star = "■" if skill in favorites else "□"
            rows.append(
                f"<tr><td class='box'>{escape(star)}</td><td>{escape(str(skill))}</td><td class='jet'>{escape(str(die))}</td></tr>"
            )
        else:
            rows.append("<tr><td class='box'>□</td><td>&nbsp;</td><td class='jet'>&nbsp;</td></tr>")
    return "\n".join(rows)


def _build_list_lines(values: list[str], total: int, with_box: bool = False) -> str:
    rows: list[str] = []
    for i in range(total):
        value = escape(values[i]) if i < len(values) else "&nbsp;"
        prefix = "<span class='line-box'>□</span>" if with_box else ""
        rows.append(f"<div class='line-row'>{prefix}<span>{value}</span></div>")
    return "\n".join(rows)


def _format_feat_line(feat: dict) -> str:
    name = (feat.get("name") or "").strip()
    prowess_points = int(feat.get("prowess_points") or 0)
    options = [str(option).strip() for option in (feat.get("options") or []) if str(option).strip()]
    limitation = (feat.get("limitation") or "").strip()

    parts: list[str] = []
    if name:
        label = f"{name} ({prowess_points} pt{'s' if prowess_points > 1 else ''} de prouesse)" if prowess_points > 0 else name
        parts.append(label)
    if options:
        parts.append(f"Options: {', '.join(options)}")
    if limitation:
        parts.append(f"Limitation: {limitation}")
    return " | ".join(parts)


def _build_advancement_lines(advancement_choices: list[dict], total_advancements: int) -> list[str]:
    option_labels = {value: label for value, label in ADVANCEMENT_OPTIONS}
    lines: list[str] = []

    for index, raw_choice in enumerate(advancement_choices[:total_advancements], start=1):
        choice = raw_choice or {}
        choice_type = str(choice.get("type") or "").strip()
        details = str(choice.get("details") or "").strip()
        label = option_labels.get(choice_type, choice_type or "Option non définie")

        line = f"{index:02d}. {label}"
        if details:
            line = f"{line} — {details}"
        lines.append(line)

    return lines


def _advancement_assets(advancement_choices: list[dict]) -> list[str]:
    lines: list[str] = []
    for raw_choice in advancement_choices:
        choice = raw_choice or {}
        if str(choice.get("type") or "").strip() != "new_edge":
            continue

        details = str(choice.get("details") or "").strip()
        if details:
            lines.append(f"Atout: {details}")
    return lines


def render_character_sheet_html(payload: dict, rules_result) -> str:
    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))

    favorites = set(payload.get("favorites") or [])
    skill_dice = _rule_attr(rules_result, "skill_dice", {}) or {}
    feats = payload.get("feats") or []
    feats_lines: list[str] = []
    for feat in feats:
        feat_line = _format_feat_line(feat)
        if feat_line:
            feats_lines.append(feat_line)

    equipment = payload.get("equipment") or {}
    armor = equipment.get("armor", "")

    advancements = int(payload.get("advancements") or 0)
    advancement_choices = payload.get("advancement_choices") or []
    advancements_values = _build_advancement_lines(advancement_choices, advancements)

    extra_assets = _rule_attr(rules_result, "extra_assets", []) or []
    advancement_assets = _advancement_assets(advancement_choices)
    merged_assets = list(extra_assets)
    for asset in advancement_assets:
        if asset not in merged_assets:
            merged_assets.append(asset)

    assets_values = [
        f"Concept: {payload.get('concept', '').strip()}",
        f"Défaut: {payload.get('flaw', '').strip()}",
        f"Atout de groupe: {payload.get('group_asset', '').strip()}",
        *[str(asset).strip() for asset in merged_assets if str(asset).strip()],
    ]

    context = {
        "name": escape(payload.get("name", "")),
        "player": escape(payload.get("player", "")),
        "concept": escape(payload.get("concept", "")),
        "rank_name": escape(str(_rule_attr(rules_result, "rank_name", ""))),
        "description": escape(""),
        "skills_rows": _build_skill_rows(skill_dice, favorites),
        "assets_lines": _build_list_lines(assets_values, 12, with_box=True),
        "feats_lines": _build_list_lines(feats_lines, 9),
        "armor": escape(armor),
        "protection": escape(str(payload.get("equipment_pe", {}).get("armor", ""))),
        "superficial_health": escape(str(_rule_attr(rules_result, "superficial_health", ""))),
        "attacks_lines": _build_list_lines([], 4),
        "profile_race": escape(""),
        "profile_gender": escape(""),
        "profile_age": escape(""),
        "equipment_lines": _build_list_lines(
            [equipment.get("weapon", ""), equipment.get("armor", ""), equipment.get("utility", "")], 6
        ),
        "notes_lines": _build_list_lines([], 6),
        "advancements_lines": _build_list_lines(advancements_values, 40),
    }
    return template.safe_substitute(context)
