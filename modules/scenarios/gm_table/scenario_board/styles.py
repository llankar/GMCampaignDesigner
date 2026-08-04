"""Theme-aware visual tokens for the dense GM Table scenario sheet."""

from __future__ import annotations

from dataclasses import dataclass

from modules.helpers import theme_manager
from modules.scenarios.gm_table.panel_skins import readable_text_color


def _mix(first: str, second: str, ratio: float) -> str:
    """Blend two six-digit hex colours without adding a UI dependency."""
    amount = max(0.0, min(1.0, ratio))
    first_rgb = tuple(int(first[index : index + 2], 16) for index in (1, 3, 5))
    second_rgb = tuple(int(second[index : index + 2], 16) for index in (1, 3, 5))
    channels = (
        round(left * (1.0 - amount) + right * amount)
        for left, right in zip(first_rgb, second_rgb, strict=True)
    )
    return "#" + "".join(f"{channel:02X}" for channel in channels)


@dataclass(frozen=True, slots=True)
class ScenarioBoardPalette:
    """Resolved colours used by one Scenario Board instance."""

    background: str
    surface: str
    border: str
    text: str
    muted: str
    control: str
    control_hover: str
    control_text: str
    info_bands: tuple[str, ...]
    scene_colors: tuple[str, ...]
    scene_text_colors: tuple[str, ...]
    section_accents: dict[str, str]


def resolve_scenario_board_palette(theme: str | None = None) -> ScenarioBoardPalette:
    """Build a board palette from the application's active theme tokens."""
    tokens = theme_manager.get_tokens(theme)
    background = tokens["panel_bg"]
    surface = tokens["panel_alt_bg"]
    accent = tokens["button_fg"]
    control = tokens["accent_button_fg"]
    control_hover = tokens["accent_button_hover"]

    scene_colors = tuple(
        _mix(accent, target, ratio)
        for target, ratio in (
            ("#FFFFFF", 0.12),
            ("#FFFFFF", 0.28),
            (surface, 0.18),
            ("#FFFFFF", 0.42),
        )
    )
    info_bands = tuple(
        _mix(surface, accent, ratio) for ratio in (0.16, 0.22, 0.28, 0.34, 0.40)
    )
    text = "#F4F7FB"
    return ScenarioBoardPalette(
        background=background,
        surface=surface,
        border=_mix(surface, accent, 0.52),
        text=text,
        muted=_mix(text, surface, 0.38),
        control=control,
        control_hover=control_hover,
        control_text=readable_text_color(control),
        info_bands=info_bands,
        scene_colors=scene_colors,
        scene_text_colors=tuple(readable_text_color(color) for color in scene_colors),
        section_accents={
            "objective": scene_colors[0],
            "secret": scene_colors[1],
            "pressure": scene_colors[3],
            "transition": scene_colors[2],
        },
    )
