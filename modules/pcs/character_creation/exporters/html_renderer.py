"""HTML rendering for Savage Fate character sheets."""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

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
    options = [str(option).strip() for option in (feat.get("options") or []) if str(option).strip()]
    limitation = (feat.get("limitation") or "").strip()

    parts: list[str] = []
    if name:
        parts.append(name)
    if options:
        parts.append(f"Options: {', '.join(options)}")
    if limitation:
        parts.append(f"Limitation: {limitation}")
    return " | ".join(parts)


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
    advancements_values = [f"{index:02d} {('■' if index <= advancements else '□')}" for index in range(1, 41)]
    extra_assets = _rule_attr(rules_result, "extra_assets", []) or []
    assets_values = [
        f"Concept: {payload.get('concept', '').strip()}",
        f"Défaut: {payload.get('flaw', '').strip()}",
        f"Atout de groupe: {payload.get('group_asset', '').strip()}",
        *[str(asset).strip() for asset in extra_assets if str(asset).strip()],
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
