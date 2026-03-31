"""Image renderer for static campaign posters."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64

import PIL
from PIL import Image, ImageDraw

from modules.campaigns.ui.graphical_display.data import CampaignGraphPayload

from .models import DEFAULT_POSTER_THEME, PosterTheme


ImageFont = getattr(PIL, "ImageFont", None)


@dataclass(frozen=True, slots=True)
class _NodeCard:
    title: str
    subtitle: str
    x: int
    y: int
    width: int
    height: int
    highlighted: bool = False


@dataclass(frozen=True, slots=True)
class _PosterLayout:
    margin: int
    header_top: int
    header_bottom: int
    arc_top: int
    arc_height: int
    arc_gap: int
    scenario_top: int
    scenario_bottom: int
    scenario_gap: int
    scenario_height: int
    max_per_arc: int
    footer_top: int
    footer_bottom: int


def render_campaign_poster(
    payload: CampaignGraphPayload,
    output_path: str | Path,
    *,
    theme: PosterTheme = DEFAULT_POSTER_THEME,
    width: int = 1920,
    height: int = 1080,
) -> Path:
    """Render a static campaign poster image and return its path."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if not hasattr(Image, "new") or not hasattr(ImageDraw, "Draw"):
        _write_placeholder_png(destination)
        return destination

    image = Image.new("RGB", (width, height), _hex(theme.background))
    draw = ImageDraw.Draw(image)
    title_font, body_font, small_font = _load_fonts(height=height)

    layout = _build_layout(payload, width=width, height=height)
    _draw_header(draw, payload, theme, title_font, body_font, layout, width)

    arcs = payload.arcs[:4]
    arc_cards = _layout_arc_cards(
        arcs,
        margin=layout.margin,
        top=layout.arc_top,
        card_height=layout.arc_height,
        gap=layout.arc_gap,
        canvas_width=width,
    )
    for card in arc_cards:
        _draw_card(draw, card, theme, body_font, small_font)

    scenario_cards = _layout_scenario_cards(
        payload,
        arc_cards,
        top=layout.scenario_top,
        max_per_arc=layout.max_per_arc,
        scenario_height=layout.scenario_height,
        gap=layout.scenario_gap,
    )
    for card in scenario_cards:
        _draw_connector(draw, card, arc_cards, theme)
        _draw_card(draw, card, theme, body_font, small_font)

    _draw_footer(draw, payload, theme, small_font, layout, width)
    image.save(destination)
    return destination


def _build_layout(payload: CampaignGraphPayload, *, width: int, height: int) -> _PosterLayout:
    margin = max(24, int(width * 0.023))
    header_top = max(20, int(height * 0.024))
    header_height = max(112, int(height * 0.125))
    header_bottom = header_top + header_height

    footer_bottom = height - header_top
    footer_height = max(118, int(height * 0.11))
    footer_top = footer_bottom - footer_height

    section_gap = max(20, int(height * 0.022))
    arc_top = header_bottom + section_gap
    arc_height = max(106, int(height * 0.115))
    scenario_top = arc_top + arc_height + section_gap
    scenario_bottom = footer_top - section_gap

    total_scenarios = sum(len(arc.scenarios) for arc in payload.arcs[:4])
    arc_count = max(1, min(4, len(payload.arcs)))
    average_per_arc = max(1, (total_scenarios + arc_count - 1) // arc_count)
    scenario_gap = max(10, int(height * 0.012))
    available = max(0, scenario_bottom - scenario_top)
    max_per_arc = max(1, min(average_per_arc, 5))

    while max_per_arc > 1:
        required_gaps = (max_per_arc - 1) * scenario_gap
        scenario_height = (available - required_gaps) // max_per_arc
        if scenario_height >= 110:
            break
        max_per_arc -= 1

    required_gaps = (max_per_arc - 1) * scenario_gap
    scenario_height = max(90, (available - required_gaps) // max_per_arc)

    return _PosterLayout(
        margin=margin,
        header_top=header_top,
        header_bottom=header_bottom,
        arc_top=arc_top,
        arc_height=arc_height,
        arc_gap=max(16, int(width * 0.01)),
        scenario_top=scenario_top,
        scenario_bottom=scenario_bottom,
        scenario_gap=scenario_gap,
        scenario_height=scenario_height,
        max_per_arc=max_per_arc,
        footer_top=footer_top,
        footer_bottom=footer_bottom,
    )


def _draw_header(
    draw: ImageDraw.ImageDraw,
    payload: CampaignGraphPayload,
    theme: PosterTheme,
    title_font,
    body_font,
    layout: _PosterLayout,
    width: int,
) -> None:
    margin = layout.margin
    draw.rounded_rectangle(
        (margin, layout.header_top, width - margin, layout.header_bottom),
        radius=20,
        fill=_hex(theme.surface),
        outline=_hex(theme.border),
        width=2,
    )
    top = layout.header_top
    draw.text((margin + 26, top + 18), payload.name or "Campaign Atlas", fill=_hex(theme.text_primary), font=title_font)

    subtitle = payload.logline or payload.setting or "Campaign update"
    draw.text((margin + 26, top + 66), _truncate(subtitle, 100), fill=_hex(theme.text_secondary), font=body_font)

    meta = f"Arcs: {len(payload.arcs)}   Scenarios: {payload.linked_scenario_count}"
    draw.text((width - margin - 420, top + 22), meta, fill=_hex(theme.accent), font=body_font)


def _layout_arc_cards(arcs, *, margin: int, top: int, card_height: int, gap: int, canvas_width: int) -> list[_NodeCard]:
    if not arcs:
        return []
    count = len(arcs)
    card_width = int((canvas_width - (margin * 2) - ((count - 1) * gap)) / count)
    cards: list[_NodeCard] = []
    for index, arc in enumerate(arcs):
        x = margin + index * (card_width + gap)
        cards.append(
            _NodeCard(
                title=_truncate(arc.name, 30),
                subtitle=_truncate(arc.status or "Planned", 50),
                x=x,
                y=top,
                width=card_width,
                height=card_height,
                highlighted=arc.status.lower() == "completed",
            )
        )
    return cards


def _layout_scenario_cards(
    payload: CampaignGraphPayload,
    arc_cards: list[_NodeCard],
    *,
    top: int,
    max_per_arc: int,
    scenario_height: int,
    gap: int,
) -> list[_NodeCard]:
    cards: list[_NodeCard] = []
    for arc_index, arc in enumerate(payload.arcs[: len(arc_cards)]):
        base = arc_cards[arc_index]
        scenarios = arc.scenarios[:max_per_arc]
        if not scenarios:
            continue
        scenario_width = base.width
        for scenario_index, scenario in enumerate(scenarios):
            y = top + scenario_index * (scenario_height + gap)
            summary = scenario.summary or scenario.objective or "No summary"
            cards.append(
                _NodeCard(
                    title=_truncate(scenario.title, 34),
                    subtitle=_wrap_text(summary, width=max(36, scenario_width // 12), max_lines=2),
                    x=base.x,
                    y=y,
                    width=scenario_width,
                    height=scenario_height,
                    highlighted=scenario.has_secrets,
                )
            )
    return cards


def _draw_card(draw: ImageDraw.ImageDraw, card: _NodeCard, theme: PosterTheme, body_font, small_font) -> None:
    fill = _hex(theme.elevated if card.highlighted else theme.surface)
    border = _hex(theme.accent if card.highlighted else theme.border)
    draw.rounded_rectangle((card.x, card.y, card.x + card.width, card.y + card.height), radius=14, fill=fill, outline=border, width=2)
    draw.text((card.x + 18, card.y + 14), card.title, fill=_hex(theme.text_primary), font=body_font)
    draw.multiline_text((card.x + 18, card.y + 54), card.subtitle, fill=_hex(theme.text_secondary), font=small_font, spacing=4)


def _draw_connector(draw: ImageDraw.ImageDraw, card: _NodeCard, arc_cards: list[_NodeCard], theme: PosterTheme) -> None:
    parent = next((arc for arc in arc_cards if arc.x == card.x), None)
    if parent is None:
        return
    start = (parent.x + parent.width // 2, parent.y + parent.height)
    end = (card.x + card.width // 2, card.y)
    draw.line((start, end), fill=_hex(theme.connector), width=2)


def _draw_footer(draw: ImageDraw.ImageDraw, payload: CampaignGraphPayload, theme: PosterTheme, small_font, layout: _PosterLayout, width: int) -> None:
    margin = layout.margin
    top = layout.footer_top
    draw.rounded_rectangle((margin, top, width - margin, layout.footer_bottom), radius=16, fill=_hex(theme.surface), outline=_hex(theme.border), width=2)
    draw.text((margin + 20, top + 18), "KNOWN FACTS", fill=_hex(theme.text_secondary), font=small_font)

    facts = [payload.main_objective, payload.stakes, payload.themes]
    cleaned = [item.strip() for item in facts if isinstance(item, str) and item.strip()]
    if not cleaned:
        cleaned = ["No campaign highlights set yet."]
    for index, fact in enumerate(cleaned[:3]):
        draw.text((margin + 20, top + 46 + (index * 24)), f"• {_truncate(fact, 140)}", fill=_hex(theme.text_primary), font=small_font)


def _truncate(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 1)].rstrip()}…"


def _wrap_text(text: str, *, width: int, max_lines: int) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    words = value.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word]).strip()
        if len(candidate) <= width:
            current.append(word)
            continue
        if current:
            lines.append(" ".join(current))
        current = [word]
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(" ".join(current))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = _truncate(lines[-1], max(4, width))
    return "\n".join(lines)


def _hex(color: str) -> str:
    value = (color or "").strip()
    if value.startswith("#") and len(value) in {4, 7}:
        return value
    return "#ffffff"


def _write_placeholder_png(path: Path) -> None:
    """Write a minimal PNG when Pillow drawing APIs are unavailable."""
    transparent_pixel = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z4x8AAAAASUVORK5CYII="
    )
    path.write_bytes(base64.b64decode(transparent_pixel))


def _load_fonts(*, height: int):
    if ImageFont is None:
        return None, None, None

    scale = max(height / 1080, 0.75)
    title_size = max(20, int(round(42 * scale)))
    body_size = max(14, int(round(28 * scale)))
    small_size = max(12, int(round(24 * scale)))

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for font_path in font_candidates:
        try:
            title = ImageFont.truetype(font_path, title_size)
            body = ImageFont.truetype(font_path, body_size)
            small = ImageFont.truetype(font_path, small_size)
            return title, body, small
        except OSError:
            continue

    fallback_font = ImageFont.load_default()
    return fallback_font, fallback_font, fallback_font
