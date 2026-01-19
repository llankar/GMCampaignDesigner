from dataclasses import dataclass

from docx.shared import Inches


@dataclass(frozen=True)
class LayoutPreset:
    key: str
    label: str
    width_in: float
    height_in: float
    margin_in: float


LAYOUT_PRESETS = (
    LayoutPreset(
        key="pocket_4x6",
        label="Pocket 4x6 (Portrait)",
        width_in=4.0,
        height_in=6.0,
        margin_in=0.3,
    ),
    LayoutPreset(
        key="pocket_4x6_landscape",
        label="Pocket 4x6 (Landscape)",
        width_in=6.0,
        height_in=4.0,
        margin_in=0.3,
    ),
    LayoutPreset(
        key="a6",
        label="A6 (Portrait)",
        width_in=4.13,
        height_in=5.83,
        margin_in=0.35,
    ),
)

DEFAULT_LAYOUT_KEY = "pocket_4x6"


def get_layout_presets() -> dict[str, LayoutPreset]:
    return {preset.key: preset for preset in LAYOUT_PRESETS}


def apply_layout(document, preset_key: str) -> LayoutPreset:
    presets = get_layout_presets()
    preset = presets.get(preset_key) or presets[DEFAULT_LAYOUT_KEY]
    section = document.sections[0]
    section.page_width = Inches(preset.width_in)
    section.page_height = Inches(preset.height_in)
    section.top_margin = Inches(preset.margin_in)
    section.bottom_margin = Inches(preset.margin_in)
    section.left_margin = Inches(preset.margin_in)
    section.right_margin = Inches(preset.margin_in)
    return preset
