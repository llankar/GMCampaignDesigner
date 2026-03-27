"""Scene list density helpers for Scenario details."""

SCENE_DENSITY_MODES = ("Compact", "Normal", "Focus")
DEFAULT_SCENE_DENSITY = "Normal"


SCENE_DENSITY_STYLES = {
    "Compact": {
        "header_height": 30,
        "header_padx": 10,
        "header_pady": (8, 2),
        "outer_padx": 16,
        "outer_pady": 5,
        "body_padx": 10,
        "body_pady": (2, 8),
        "description_font_size": 12,
        "collapse_secondary_by_default": True,
    },
    "Normal": {
        "header_height": 38,
        "header_padx": 14,
        "header_pady": (12, 4),
        "outer_padx": 20,
        "outer_pady": 8,
        "body_padx": 14,
        "body_pady": (4, 12),
        "description_font_size": 13,
        "collapse_secondary_by_default": False,
    },
    "Focus": {
        "header_height": 46,
        "header_padx": 16,
        "header_pady": (14, 6),
        "outer_padx": 24,
        "outer_pady": 10,
        "body_padx": 16,
        "body_pady": (6, 14),
        "description_font_size": 14,
        "collapse_secondary_by_default": False,
    },
}


def normalize_scene_density(value):
    return value if value in SCENE_DENSITY_MODES else DEFAULT_SCENE_DENSITY


def get_scene_density_style(mode):
    return SCENE_DENSITY_STYLES[normalize_scene_density(mode)]
