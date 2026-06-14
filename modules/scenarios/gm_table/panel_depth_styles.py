"""Decorative depth-layer styles for GM Table floating panels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DepthLayerStyle:
    """A sibling frame rendered behind a real panel."""

    offset_x: int
    offset_y: int
    expand_width: int
    expand_height: int
    color: str
    border_color: str | None = None
    border_width: int = 0
    corner_radius: int = 24


@dataclass(frozen=True, slots=True)
class EdgeAccentStyle:
    """A thin inner edge accent rendered on top of a panel."""

    side: str
    color: str
    thickness: int = 3
    inset: int = 8


@dataclass(frozen=True, slots=True)
class PanelDepthStyle:
    """Complete decorative style bundle for a panel skin."""

    shadow_layers: tuple[DepthLayerStyle, ...]
    edge_accents: tuple[EdgeAccentStyle, ...]
    stack_strip_side: str | None = None
    stack_strip_color: str | None = None
    stack_strip_width: int = 8


_COMMON_EDGE_ACCENTS = (
    EdgeAccentStyle("top", "#2E4260", thickness=1, inset=12),
    EdgeAccentStyle("left", "#273C58", thickness=1, inset=12),
    EdgeAccentStyle("right", "#070B15", thickness=2, inset=12),
    EdgeAccentStyle("bottom", "#070B15", thickness=2, inset=12),
)

_DEFAULT_STYLE = PanelDepthStyle(
    shadow_layers=(DepthLayerStyle(10, 14, 0, 0, "#040810", corner_radius=24),),
    edge_accents=_COMMON_EDGE_ACCENTS,
)

_SKIN_DEPTH_STYLES: dict[str, PanelDepthStyle] = {
    # Fleet Admiral binder — navy shadows, no side strip
    "binder": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(10, 14, 0, 0, "#040810", corner_radius=24),
            DepthLayerStyle(4, 5, 0, 0, "#0A1530", border_color="#1B3565", border_width=1, corner_radius=24),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#305080", thickness=1, inset=12),
            EdgeAccentStyle("left", "#2A4A78", thickness=1, inset=12),
            EdgeAccentStyle("right", "#07101C", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#07101C", thickness=2, inset=12),
        ),
    ),
    # Shadow Archive dossier — indigo shadows, violet strip
    "dossier": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(10, 14, 0, 0, "#04050E", corner_radius=24),
            DepthLayerStyle(4, 5, 0, 0, "#0E0F28", border_color="#2C2E72", border_width=1, corner_radius=24),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#343668", thickness=1, inset=12),
            EdgeAccentStyle("left", "#2E3060", thickness=1, inset=12),
            EdgeAccentStyle("right", "#070810", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#070810", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#A855F7",
        stack_strip_width=6,
    ),
    # Obsidian Archive paper_stack — cold blue shadows, sky-blue strip
    "paper_stack": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(10, 14, 0, 0, "#040810", corner_radius=24),
            DepthLayerStyle(4, 5, 0, 0, "#0A1428", border_color="#1A3256", border_width=1, corner_radius=24),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#2A4870", thickness=1, inset=12),
            EdgeAccentStyle("left", "#243E68", thickness=1, inset=12),
            EdgeAccentStyle("right", "#07101C", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#07101C", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#0EB4E7",
        stack_strip_width=6,
    ),
    # Forest Cartographer parchment — forest shadows, emerald strip
    "parchment": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(10, 14, 0, 0, "#030A08", corner_radius=24),
            DepthLayerStyle(4, 5, 0, 0, "#091814", border_color="#165C3C", border_width=1, corner_radius=24),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#226048", thickness=1, inset=12),
            EdgeAccentStyle("left", "#1E5440", thickness=1, inset=12),
            EdgeAccentStyle("right", "#060E0A", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#060E0A", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#10C97C",
        stack_strip_width=6,
    ),
    # Inkmaster Archive index_cards — navy shadows, warm amber strip
    "index_cards": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(10, 14, 0, 0, "#040810", corner_radius=24),
            DepthLayerStyle(4, 5, 0, 0, "#0D1526", border_color="#1E3458", border_width=1, corner_radius=24),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#2E4870", thickness=1, inset=12),
            EdgeAccentStyle("left", "#283E68", thickness=1, inset=12),
            EdgeAccentStyle("right", "#07101C", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#07101C", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#F59E0B",
        stack_strip_width=6,
    ),
    # Obsidian Codex slate — near-black teal shadows, no strip
    "slate": PanelDepthStyle(
        shadow_layers=(DepthLayerStyle(10, 14, 0, 0, "#02080A", corner_radius=24),),
        edge_accents=(
            EdgeAccentStyle("top", "#246860", thickness=1, inset=12),
            EdgeAccentStyle("left", "#1E5C55", thickness=1, inset=12),
            EdgeAccentStyle("right", "#040C0A", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#040C0A", thickness=2, inset=12),
        ),
    ),
}


def resolve_panel_depth_style(skin_name: str) -> PanelDepthStyle:
    """Return decorative depth styling for a resolved panel skin name."""
    return _SKIN_DEPTH_STYLES.get(skin_name, _DEFAULT_STYLE)
