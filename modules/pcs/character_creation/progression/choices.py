"""Definitions for advancement choices displayed in the UI."""

ADVANCEMENT_OPTIONS = [
    ("new_edge", "+1 Atout (limité à 1 fois par Rang)"),
    (
        "superficial_health",
        "+5 Blessures Superficielles (+10 pour un Super-Héros, limité à 1 fois par Rang)",
    ),
    (
        "prowess_points",
        "+ Points de Prouesse (1 + Rang actuel, limité à 1 fois par Rang)",
    ),
    ("equipment_points", "Équipement : PE gagnés = 4 + Rang actuel"),
    (
        "skill_improvement",
        "Amélioration de compétences : 2 favorites (+1 dé) ou 1 non-favorite (+1 dé)",
    ),
]
