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


def render_character_sheet_html(payload: dict, rules_result) -> str:
    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))

    favorites = set(payload.get("favorites") or [])
    skill_dice = _rule_attr(rules_result, "skill_dice", {}) or {}
    skills_rows = []
    for skill, die in skill_dice.items():
        star = "★" if skill in favorites else ""
        skills_rows.append(
            f"<tr><td class='fav'>{escape(star)}</td><td>{escape(str(skill))}</td><td>{escape(str(die))}</td></tr>"
        )

    feats = payload.get("feats") or []
    feats_items = []
    for index, feat in enumerate(feats, start=1):
        options = "".join(f"<li>{escape(str(option))}</li>" for option in (feat.get("options") or []) if option)
        feats_items.append(
            "".join(
                [
                    f"<h3>{index}. {escape(feat.get('name', f'Prouesse {index}'))}</h3>",
                    f"<ul>{options}</ul>" if options else "<p class='small'>Aucune option.</p>",
                    f"<p class='small'><strong>Limitation:</strong> {escape(feat.get('limitation', ''))}</p>",
                ]
            )
        )

    pe = payload.get("equipment_pe") or {}
    equipment = payload.get("equipment") or {}
    advancements = int(payload.get("advancements") or 0)
    marks = " ".join(f"{i:02d}:[{'X' if i <= advancements else ' '} ]" for i in range(1, 41))

    context = {
        "name": escape(payload.get("name", "")),
        "player": escape(payload.get("player", "")),
        "concept": escape(payload.get("concept", "")),
        "flaw": escape(payload.get("flaw", "")),
        "group_asset": escape(payload.get("group_asset", "")),
        "rank_name": escape(str(_rule_attr(rules_result, "rank_name", ""))),
        "rank_index": escape(str(_rule_attr(rules_result, "rank_index", ""))),
        "superficial_health": escape(str(_rule_attr(rules_result, "superficial_health", ""))),
        "skills_rows": "\n".join(skills_rows) or "<tr><td colspan='3'>Aucune compétence</td></tr>",
        "feats_html": "\n".join(feats_items) or "<p class='small'>Aucune prouesse.</p>",
        "weapon": escape(equipment.get("weapon", "")),
        "armor": escape(equipment.get("armor", "")),
        "utility": escape(equipment.get("utility", "")),
        "weapon_pe": escape(str(pe.get("weapon", 0))),
        "armor_pe": escape(str(pe.get("armor", 0))),
        "utility_pe": escape(str(pe.get("utility", 0))),
        "advancements_marks": escape(marks),
    }
    return template.safe_substitute(context)
