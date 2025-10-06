from __future__ import annotations

from typing import Any, Dict, List

from modules.helpers.logging_helper import log_module_import, log_warning

log_module_import(__name__)


def build_token_macros(actions: List[Dict[str, Any]], *, token_name: str | None = None) -> List[Dict[str, str]]:
    """Return MapTool-style macro definitions for the provided actions."""

    macros: List[Dict[str, str]] = []
    if not actions:
        return macros

    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            continue
        label = str(action.get("label") or f"Action {index}")
        attack_formula = _normalize_formula(action.get("attack_roll_formula"))
        damage_formula = _normalize_formula(action.get("damage_formula"))
        notes = str(action.get("notes") or "").strip()

        if not attack_formula and not damage_formula:
            log_warning(
                f"Skipping MapTool macro for '{label}' – no roll formulas available.",
                func_name="maptools.build_token_macros",
            )
            continue

        commands: List[str] = []
        if attack_formula:
            commands.append(f"/r {attack_formula} [Attack]")
        if damage_formula:
            commands.append(f"/r {damage_formula} [Damage]")
        if notes:
            commands.append(f"// Notes: {notes}")

        macros.append(
            {
                "label": label,
                "commands": "\n".join(commands),
            }
        )

    if not macros and token_name:
        log_warning(
            f"No MapTool macros generated for token '{token_name}'.",
            func_name="maptools.build_token_macros",
        )
    return macros


def _normalize_formula(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text
