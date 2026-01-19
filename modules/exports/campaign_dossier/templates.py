from docx.shared import Pt, RGBColor

from modules.helpers.theme_manager import THEME_DEFAULT, THEME_MEDIEVAL, THEME_SF


THEME_STYLES = {
    THEME_DEFAULT: {
        "name": "Modern Agency",
        "font": "Calibri",
        "heading_font": "Franklin Gothic Medium",
        "accent": RGBColor(32, 70, 130),
    },
    THEME_MEDIEVAL: {
        "name": "Medieval Codex",
        "font": "Garamond",
        "heading_font": "Garamond",
        "accent": RGBColor(88, 52, 32),
    },
    THEME_SF: {
        "name": "Sci-Fi Terminal",
        "font": "Consolas",
        "heading_font": "Consolas",
        "accent": RGBColor(0, 180, 160),
    },
}

MIN_FONT_SIZE_PT = 14


def _apply_font_size(font, size_pt: float) -> None:
    font.size = Pt(max(size_pt, MIN_FONT_SIZE_PT))


def apply_dossier_theme(document, theme_key: str) -> dict:
    style = THEME_STYLES.get(theme_key) or THEME_STYLES[THEME_DEFAULT]

    normal = document.styles["Normal"]
    normal.font.name = style["font"]
    _apply_font_size(normal.font, 9)

    for level in range(1, 4):
        style_name = f"Heading {level}"
        try:
            heading = document.styles[style_name]
        except KeyError:
            continue
        heading.font.name = style["heading_font"]
        heading.font.color.rgb = style["accent"]
        if level == 1:
            _apply_font_size(heading.font, 16)
        elif level == 2:
            _apply_font_size(heading.font, 12)
        else:
            _apply_font_size(heading.font, 10)

    return style
