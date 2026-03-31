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

    margin = 44
    _draw_header(draw, payload, theme, title_font, body_font, margin, width, height)

    arcs = payload.arcs[:4]
    arc_cards = _layout_arc_cards(arcs, margin=margin, top=176, canvas_width=width)
    for card in arc_cards:
        _draw_card(draw, card, theme, body_font, small_font)

    scenario_cards = _layout_scenario_cards(payload, arc_cards, top=392, max_per_arc=3)
    for card in scenario_cards:
        _draw_connector(draw, card, arc_cards, theme)
        _draw_card(draw, card, theme, body_font, small_font)

    _draw_footer(draw, payload, theme, small_font, margin, width, height)
    image.save(destination)
    return destination


def _draw_header(
    draw: ImageDraw.ImageDraw,
    payload: CampaignGraphPayload,
    theme: PosterTheme,
    title_font,
    body_font,
    margin: int,
    width: int,
    height: int,
) -> None:
    header_bottom = 162 if height >= 1080 else 146
    draw.rounded_rectangle(
        (margin, 28, width - margin, header_bottom),
        radius=20,
        fill=_hex(theme.surface),
        outline=_hex(theme.border),
        width=2,
    )
    draw.text((margin + 26, 46), payload.name or "Campaign Atlas", fill=_hex(theme.text_primary), font=title_font)

    subtitle = payload.logline or payload.setting or "Campaign update"
    draw.text((margin + 26, 98), _truncate(subtitle, 100), fill=_hex(theme.text_secondary), font=body_font)

    meta = f"Arcs: {len(payload.arcs)}   Scenarios: {payload.linked_scenario_count}"
    draw.text((width - margin - 420, 50), meta, fill=_hex(theme.accent), font=body_font)


def _layout_arc_cards(arcs, *, margin: int, top: int, canvas_width: int) -> list[_NodeCard]:
    if not arcs:
        return []
    gap = 20
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
                height=120,
                highlighted=arc.status.lower() == "completed",
            )
        )
    return cards


def _layout_scenario_cards(payload: CampaignGraphPayload, arc_cards: list[_NodeCard], *, top: int, max_per_arc: int) -> list[_NodeCard]:
    cards: list[_NodeCard] = []
    for arc_index, arc in enumerate(payload.arcs[: len(arc_cards)]):
        base = arc_cards[arc_index]
        scenarios = arc.scenarios[:max_per_arc]
        if not scenarios:
            continue
        gap = 14
        scenario_width = base.width
        scenario_height = 96
        for scenario_index, scenario in enumerate(scenarios):
            y = top + scenario_index * (scenario_height + gap)
            cards.append(
                _NodeCard(
                    title=_truncate(scenario.title, 34),
                    subtitle=_truncate(scenario.summary or scenario.objective or "No summary", 72),
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
    draw.text((card.x + 18, card.y + 54), card.subtitle, fill=_hex(theme.text_secondary), font=small_font)


def _draw_connector(draw: ImageDraw.ImageDraw, card: _NodeCard, arc_cards: list[_NodeCard], theme: PosterTheme) -> None:
    parent = next((arc for arc in arc_cards if arc.x == card.x), None)
    if parent is None:
        return
    start = (parent.x + parent.width // 2, parent.y + parent.height)
    end = (card.x + card.width // 2, card.y)
    draw.line((start, end), fill=_hex(theme.connector), width=2)


def _draw_footer(draw: ImageDraw.ImageDraw, payload: CampaignGraphPayload, theme: PosterTheme, small_font, margin: int, width: int, height: int) -> None:
    top = height - 146
    draw.rounded_rectangle((margin, top, width - margin, height - 28), radius=16, fill=_hex(theme.surface), outline=_hex(theme.border), width=2)
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
