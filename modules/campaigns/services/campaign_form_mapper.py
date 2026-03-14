from __future__ import annotations

from typing import Any

from modules.helpers.text_helpers import coerce_text, deserialize_possible_json


def list_campaign_names(campaign_items: list[dict]) -> list[str]:
    """Return sorted campaign names for UI selectors."""

    names: list[str] = []
    for item in campaign_items:
        name = str(item.get("Name") or "").strip()
        if name and name not in names:
            names.append(name)
    return sorted(names, key=str.casefold)


def build_form_state_from_campaign(campaign_data: dict) -> tuple[dict, dict, list[dict]]:
    """Map a stored campaign payload to wizard form vars, textareas and arcs."""

    form_vars = {
        "name": coerce_text(campaign_data.get("Name")).strip(),
        "genre": coerce_text(campaign_data.get("Genre")).strip(),
        "tone": coerce_text(campaign_data.get("Tone")).strip(),
        "status": coerce_text(campaign_data.get("Status") or "Planned").strip() or "Planned",
        "start_date": coerce_text(campaign_data.get("StartDate")).strip(),
        "end_date": coerce_text(campaign_data.get("EndDate")).strip(),
    }

    themes = campaign_data.get("Themes")
    if isinstance(themes, str):
        themes_text = themes
    else:
        themes_text = "\n".join(coerce_text(theme).strip() for theme in (themes or []) if coerce_text(theme).strip())

    text_areas = {
        "logline": coerce_text(campaign_data.get("Logline")).strip(),
        "setting": coerce_text(campaign_data.get("Setting")).strip(),
        "main_objective": coerce_text(campaign_data.get("MainObjective")).strip(),
        "stakes": coerce_text(campaign_data.get("Stakes")).strip(),
        "themes": themes_text,
        "notes": coerce_text(campaign_data.get("Notes")).strip(),
    }

    arcs_data = _coerce_arcs_payload(campaign_data.get("Arcs"))
    arcs: list[dict] = []
    for arc in arcs_data:
        if not isinstance(arc, dict):
            continue
        arcs.append(
            {
                "name": coerce_text(arc.get("name")).strip(),
                "summary": coerce_text(arc.get("summary")).strip(),
                "objective": coerce_text(arc.get("objective")).strip(),
                "status": coerce_text(arc.get("status") or "Planned").strip() or "Planned",
                "scenarios": [coerce_text(v).strip() for v in (arc.get("scenarios") or []) if coerce_text(v).strip()],
            }
        )

    return form_vars, text_areas, arcs



def _coerce_arcs_payload(raw_arcs: Any) -> list[dict]:
    parsed = deserialize_possible_json(raw_arcs)

    if isinstance(parsed, dict):
        text_value = parsed.get("text")
        if text_value is not None:
            return _coerce_arcs_payload(text_value)

        nested_arcs = parsed.get("arcs")
        if isinstance(nested_arcs, list):
            return [arc for arc in nested_arcs if isinstance(arc, dict)]

        arc_keys = {"name", "summary", "objective", "status", "scenarios"}
        if any(key in parsed for key in arc_keys):
            return [parsed]
        return []

    if isinstance(parsed, list):
        return [arc for arc in parsed if isinstance(arc, dict)]

    return []
