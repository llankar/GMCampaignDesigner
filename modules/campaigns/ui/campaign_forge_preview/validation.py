from __future__ import annotations

from modules.campaigns.ui.campaign_forge_preview.models import ForgeValidationResult


def evaluate_forge_warnings(generated_payload: dict) -> ForgeValidationResult:
    result = ForgeValidationResult()

    for arc_group in generated_payload.get("arcs") or []:
        arc_name = str(arc_group.get("arc_name") or "Unnamed arc").strip() or "Unnamed arc"
        for scenario in arc_group.get("scenarios") or []:
            title = str(scenario.get("Title") or "Untitled scenario").strip() or "Untitled scenario"
            warnings: list[str] = []

            scenes = scenario.get("Scenes") or []
            if not isinstance(scenes, list):
                scenes = []
            if not scenes:
                warnings.append("missing scenes")

            if scenes and not _contains_stakes(scenes):
                warnings.append("empty stakes")

            places = _normalize_name_list(scenario.get("Places"))
            villains = _normalize_name_list(scenario.get("Villains"))
            factions = _normalize_name_list(scenario.get("Factions"))
            link_signal = int(bool(places)) + int(bool(villains)) + int(bool(factions))
            if link_signal <= 1:
                warnings.append("weak links")

            if warnings:
                result.scenario_warnings[(arc_name.casefold(), title.casefold())] = warnings
                result.global_warnings.append(f"{arc_name} / {title}: {', '.join(warnings)}")

    if not result.global_warnings:
        result.global_warnings.append("No validation warnings detected.")

    return result


def _normalize_name_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _contains_stakes(scenes: list) -> bool:
    for scene in scenes:
        text = str(scene or "").strip()
        if not text:
            continue
        if "stakes:" in text.casefold():
            return True
    return False
