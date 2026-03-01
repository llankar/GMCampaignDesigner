"""Prowess-option catalog and point-cost helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProwessOption:
    name: str
    description: str
    variable_points: bool = False


PROWESS_OPTIONS = [
    ProwessOption("Bonus dommages", "+dommage (choisir 1 à 3 points).", variable_points=True),
    ProwessOption("Armure", "+armure (choisir 1 à 3 points).", variable_points=True),
    ProwessOption("Perce Armure", "Ignore 3 d'armure (max 2 fois, ou 4 fois pour Super Héros)."),
    ProwessOption("Utilisation non conventionnelle", "Permet d'utiliser une compétence à la place d'une autre."),
    ProwessOption("Effet particulier", "Effet de prouesse variable (choisir 1 à 3 points).", variable_points=True),
    ProwessOption("Durée étendue", "Un effet qui dure une scène."),
    ProwessOption("Portée étendue", "La prouesse fonctionne au-delà de la ligne de vue."),
    ProwessOption("Zone d'effet", "Affecte un groupe (effet variable de 1 à 3 points).", variable_points=True),
    ProwessOption("Bonus aux jets", "+1 sur un jet (max 2 fois)."),
    ProwessOption("Limitation de l'effet", "Ajoute une contrainte (1/scène, atout, condition, etc.)."),
    ProwessOption("Compétence*", "D12 en compétence ou +2 après D12 (Super Héros uniquement)."),
    ProwessOption("Vitesse*", "Mouvement X2 puis jusqu'à des paliers extrêmes (Super Héros uniquement)."),
]

PROWESS_OPTION_LABELS = [f"{option.name} — {option.description}" for option in PROWESS_OPTIONS]
PROWESS_OPTION_BY_LABEL = {label: option.name for label, option in zip(PROWESS_OPTION_LABELS, PROWESS_OPTIONS)}
PROWESS_OPTION_BY_NAME = {option.name: option for option in PROWESS_OPTIONS}
DEFAULT_OPTION_NAME = PROWESS_OPTIONS[0].name


def option_uses_variable_points(option_name: str) -> bool:
    return PROWESS_OPTION_BY_NAME.get(option_name, PROWESS_OPTIONS[0]).variable_points


def parse_variable_points(option_detail: str) -> int:
    """Extract point level from details, defaulting to 1 when absent or invalid."""

    for token in (option_detail or "").replace("pt", " ").split():
        if token.isdigit():
            numeric = int(token)
            if 1 <= numeric <= 3:
                return numeric
    return 1

