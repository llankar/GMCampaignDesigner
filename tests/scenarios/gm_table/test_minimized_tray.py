from modules.scenarios.gm_table.minimized_tray import (
    MINIMIZED_TRAY_BUTTON_GAP,
    MINIMIZED_TRAY_BUTTON_WIDTH,
    compact_tray_title,
    minimized_tray_button_style,
    minimized_tray_columns,
)
from modules.scenarios.gm_table.panel_skins import resolve_panel_skin


def test_minimized_tray_button_style_uses_spine_for_book_skin() -> None:
    skin = resolve_panel_skin("campaign_dashboard", {})

    style = minimized_tray_button_style(skin)

    assert style["fg_color"] == skin.border_color
    assert style["border_color"] == skin.accent_color
    assert style["text_color"] == "#F8FAFC"


def test_minimized_tray_button_style_uses_tab_for_file_skin() -> None:
    skin = resolve_panel_skin("entity", {"entity_type": "NPCs"})

    style = minimized_tray_button_style(skin)

    assert style["fg_color"] == skin.header_color
    assert style["hover_color"] == skin.accent_color
    assert style["border_color"] == skin.border_color


def test_minimized_tray_button_style_keeps_paper_skin_readable() -> None:
    skin = resolve_panel_skin("handouts", {})

    style = minimized_tray_button_style(skin)

    assert style["fg_color"] == skin.body_color
    assert style["text_color"] == "#F8FAFC"


def test_compact_tray_title_normalizes_and_truncates_long_titles() -> None:
    assert (
        compact_tray_title("  Villain    Master Plan Notes  ") == "Villain Master Pl…"
    )
    assert compact_tray_title("") == "Panel"


def test_minimized_tray_columns_keeps_small_width_to_single_column() -> None:
    assert minimized_tray_columns(1) == 1
    assert minimized_tray_columns(MINIMIZED_TRAY_BUTTON_WIDTH) == 1
    assert (
        minimized_tray_columns(
            (MINIMIZED_TRAY_BUTTON_WIDTH + MINIMIZED_TRAY_BUTTON_GAP) * 2
        )
        == 2
    )
