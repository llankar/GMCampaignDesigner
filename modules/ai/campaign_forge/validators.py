"""Validation helpers for campaign forge."""
from __future__ import annotations

from typing import Any


class CampaignForgeValidationError(ValueError):
    """Raised when campaign forge data is incomplete or structurally invalid."""


def validate_foundation(foundation: dict[str, Any]) -> None:
    """Validate foundation."""
    required = {
        "name": "Campaign name is required.",
        "logline": "Campaign logline is required.",
        "main_objective": "Campaign main objective is required.",
    }
    for field_name, message in required.items():
        if not str(foundation.get(field_name) or "").strip():
            raise CampaignForgeValidationError(message)


def validate_arcs(arcs: list[dict[str, Any]], *, min_arcs: int = 1) -> None:
    """Validate arcs."""
    if len(arcs) < min_arcs:
        raise CampaignForgeValidationError(f"At least {min_arcs} arc(s) are required.")

    for index, arc in enumerate(arcs, start=1):
        # Process each (index, arc) from enumerate(arcs, start=1).
        if not str(arc.get("name") or "").strip():
            raise CampaignForgeValidationError(f"Arc #{index} is missing 'name'.")
        if not isinstance(arc.get("scenarios"), list) or not arc.get("scenarios"):
            raise CampaignForgeValidationError(
                f"Arc '{arc.get('name') or index}' must include at least one linked scenario."
            )


def validate_generated_payload(
    payload: dict[str, Any],
    *,
    expected_arc_count: int,
    scenarios_per_arc: int = 2,
    required_scenario_fields: tuple[str, ...] = ("Title", "Summary", "Scenes"),
) -> None:
    """Validate generated payload."""
    groups = payload.get("arcs")
    if not isinstance(groups, list):
        raise CampaignForgeValidationError("Generated payload must include an 'arcs' list.")
    if len(groups) != expected_arc_count:
        raise CampaignForgeValidationError(
            f"Generated payload must include exactly {expected_arc_count} arc groups; got {len(groups)}."
        )

    for group in groups:
        # Process each group from groups.
        if not isinstance(group, dict):
            raise CampaignForgeValidationError("Each generated arc group must be an object.")
        arc_name = str(group.get("arc_name") or "").strip()
        if not arc_name:
            raise CampaignForgeValidationError("Each generated arc group must include 'arc_name'.")
        scenarios = group.get("scenarios")
        if not isinstance(scenarios, list):
            raise CampaignForgeValidationError(f"Arc '{arc_name}' must include a scenarios list.")
        if len(scenarios) != scenarios_per_arc:
            raise CampaignForgeValidationError(
                f"Arc '{arc_name}' must include exactly {scenarios_per_arc} scenario(s)."
            )

        for scenario in scenarios:
            # Process each scenario from scenarios.
            if not isinstance(scenario, dict):
                raise CampaignForgeValidationError(f"Arc '{arc_name}' includes a non-object scenario payload.")
            for field_name in required_scenario_fields:
                # Process each field_name from required_scenario_fields.
                value = scenario.get(field_name)
                if field_name == "Scenes":
                    # Handle the branch where field_name == 'Scenes'.
                    if not isinstance(value, list) or not value:
                        raise CampaignForgeValidationError(
                            f"Scenario in arc '{arc_name}' must include a non-empty Scenes list."
                        )
                    continue
                if not str(value or "").strip():
                    raise CampaignForgeValidationError(
                        f"Scenario in arc '{arc_name}' is missing required field '{field_name}'."
                    )
