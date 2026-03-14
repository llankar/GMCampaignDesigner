from __future__ import annotations


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
        "name": str(campaign_data.get("Name") or "").strip(),
        "genre": str(campaign_data.get("Genre") or "").strip(),
        "tone": str(campaign_data.get("Tone") or "").strip(),
        "status": str(campaign_data.get("Status") or "Planned").strip() or "Planned",
        "start_date": str(campaign_data.get("StartDate") or "").strip(),
        "end_date": str(campaign_data.get("EndDate") or "").strip(),
    }

    themes = campaign_data.get("Themes")
    if isinstance(themes, str):
        themes_text = themes
    else:
        themes_text = "\n".join(str(theme).strip() for theme in (themes or []) if str(theme).strip())

    text_areas = {
        "logline": str(campaign_data.get("Logline") or "").strip(),
        "setting": str(campaign_data.get("Setting") or "").strip(),
        "main_objective": str(campaign_data.get("MainObjective") or "").strip(),
        "stakes": str(campaign_data.get("Stakes") or "").strip(),
        "themes": themes_text,
        "notes": str(campaign_data.get("Notes") or "").strip(),
    }

    arcs_data = campaign_data.get("Arcs") or []
    arcs: list[dict] = []
    for arc in arcs_data:
        if not isinstance(arc, dict):
            continue
        arcs.append(
            {
                "name": str(arc.get("name") or "").strip(),
                "summary": str(arc.get("summary") or "").strip(),
                "objective": str(arc.get("objective") or "").strip(),
                "status": str(arc.get("status") or "Planned").strip() or "Planned",
                "scenarios": list(arc.get("scenarios") or []),
            }
        )

    return form_vars, text_areas, arcs

