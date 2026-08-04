"""Presentation content for the scenario board's reference bands."""

from __future__ import annotations

from modules.scenarios.gm_table.scenario_board.models import ScenarioBoardData

InfoBand = tuple[str, tuple[tuple[str, str], ...], str]
Directive = tuple[str, str, str]
ENTITY_ACTIONS = (
    ("Open NPCs", "NPCs"),
    ("Open Creatures", "Creatures"),
    ("Open Places", "Places"),
)


def build_info_bands(data: ScenarioBoardData) -> tuple[InfoBand, ...]:
    """Return the headings and entity links displayed above the scene grid."""
    return (
        ("OBJECTIVES", (), data.objective or data.summary),
        (
            "MAJOR NPCS",
            tuple(("NPCs", name) for name in data.linked_entities.get("NPCs", ())),
            "",
        ),
        (
            "CREATURES",
            tuple(
                ("Creatures", name)
                for name in data.linked_entities.get("Creatures", ())
            ),
            "",
        ),
        (
            "FACTIONS",
            tuple(
                ("Factions", name)
                for name in data.linked_entities.get("Factions", ())
            ),
            "",
        ),
        (
            "PLACES",
            tuple(("Places", name) for name in data.linked_entities.get("Places", ())),
            "",
        ),
    )


def build_directives(data: ScenarioBoardData) -> tuple[Directive, ...]:
    """Return the non-duplicated scenario directives below the reference bands."""
    return (
        ("SECRET", data.secrets, "secret"),
        ("PRESSURE", data.pressure or data.status, "pressure"),
    )
