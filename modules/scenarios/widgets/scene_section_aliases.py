"""Alias definitions used by the scene sections parser."""

SECTION_KEY_ALIASES = {
    "key beats": "key beats",
    "conflicts/obstacles": "conflicts/obstacles",
    "conflicts / obstacles": "conflicts/obstacles",
    "conflicts": "conflicts/obstacles",
    "obstacles": "conflicts/obstacles",
    "conflits": "conflicts/obstacles",
    "conflits/obstacles": "conflicts/obstacles",
    "conflits / obstacles": "conflicts/obstacles",
    "clues/hooks": "clues/hooks",
    "clues / hooks": "clues/hooks",
    "clues": "clues/hooks",
    "hooks": "clues/hooks",
    "transitions": "transitions",
    "important locations": "important locations",
    "locations": "important locations",
    "involved npcs": "involved npcs",
    "npcs": "involved npcs",
}

CANONICAL_SECTION_KEYS = tuple(dict.fromkeys(SECTION_KEY_ALIASES.values()))

