from dataclasses import dataclass

from docx.shared import Inches, Pt


@dataclass(frozen=True)
class LayoutPreset:
    key: str
    label: str
    width_in: float
    height_in: float
    margin_in: float
    header_text: str | None = None
    footer_text: str | None = None
    min_font_size_pt: float | None = None
    paragraph_space_before_pt: float | None = None
    paragraph_space_after_pt: float | None = None
    line_spacing: float | None = None
    entity_label_format: str | None = None


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
    LayoutPreset(
        key="binder_100_pocket",
        label="Binder (100-pocket)",
        width_in=8.5,
        height_in=11.0,
        margin_in=0.6,
        min_font_size_pt=11,
        paragraph_space_before_pt=2,
        paragraph_space_after_pt=3,
        line_spacing=1.15,
    ),
)

DEFAULT_LAYOUT_KEY = "pocket_4x6"
DEFAULT_BRANDING_HEADER = "Binder Reference"
DEFAULT_BRANDING_FOOTER = "GMCampaignDesigner"


def get_layout_presets() -> dict[str, LayoutPreset]:
    return {preset.key: preset for preset in LAYOUT_PRESETS}


def _apply_header_footer(section, preset: LayoutPreset, include_branding: bool) -> None:
    if not include_branding:
        return
    header_text = preset.header_text or DEFAULT_BRANDING_HEADER
    footer_text = preset.footer_text or DEFAULT_BRANDING_FOOTER
    if header_text:
        header_paragraph = section.header.paragraphs[0]
        header_paragraph.text = header_text
    if footer_text:
        footer_paragraph = section.footer.paragraphs[0]
        footer_paragraph.text = footer_text


def _apply_document_style(document, preset: LayoutPreset) -> None:
    if preset.min_font_size_pt is None:
        return
    normal_style = document.styles["Normal"]
    normal_style.font.size = Pt(preset.min_font_size_pt)
    paragraph_format = normal_style.paragraph_format
    if preset.paragraph_space_before_pt is not None:
        paragraph_format.space_before = Pt(preset.paragraph_space_before_pt)
    if preset.paragraph_space_after_pt is not None:
        paragraph_format.space_after = Pt(preset.paragraph_space_after_pt)
    if preset.line_spacing is not None:
        paragraph_format.line_spacing = preset.line_spacing


def format_entity_label(preset: LayoutPreset, entity_label: str, name: str) -> str:
    if preset.entity_label_format:
        return preset.entity_label_format.format(entity=entity_label, name=name)
    return name


def apply_layout(document, preset_key: str, include_branding: bool = False) -> LayoutPreset:
    presets = get_layout_presets()
    preset = presets.get(preset_key) or presets[DEFAULT_LAYOUT_KEY]
    section = document.sections[0]
    section.page_width = Inches(preset.width_in)
    section.page_height = Inches(preset.height_in)
    section.top_margin = Inches(preset.margin_in)
    section.bottom_margin = Inches(preset.margin_in)
    section.left_margin = Inches(preset.margin_in)
    section.right_margin = Inches(preset.margin_in)
    _apply_header_footer(section, preset, include_branding)
    _apply_document_style(document, preset)
    return preset
