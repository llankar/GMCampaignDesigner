"""Savage Fate constants for character creation and progression."""

SKILLS = [
    "Artisanat", "Athlétisme", "Combat", "Commandement", "Discrétion", "Enquête",
    "Érudition", "Informatique", "Jeu", "Médecine", "Perception", "Persuasion",
    "Pilotage", "Relation", "Représentation", "Ressource", "Sorcellerie", "Subornation",
    "Survie", "Technologie", "Tir", "Vol",
]

DIE_STEPS = {
    0: "-",
    1: "d4",
    2: "d6",
    3: "d8",
    4: "d10",
    5: "d12",
    6: "d12+1",
    7: "d12+2",
    8: "d12+3",
    9: "d12+4",
}

RANK_TABLE = [
    (0, 3, "Novice", 5),
    (4, 7, "Expérimenté", 5),
    (8, 11, "Vétéran", 6),
    (12, 15, "Héroïque", 6),
    (16, 19, "Légendaire", 7),
    (20, 23, "Incroyable", 7),
    (24, 27, "Surnaturel", 7),
    (28, 31, "Incroyable II", 8),
    (32, 35, "Superbe", 8),
    (36, 39, "Hors norme", 8),
    (40, 43, "Demi-dieu", 9),
]
