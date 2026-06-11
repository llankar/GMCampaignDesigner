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
    corner_radius: int = 22


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
    EdgeAccentStyle("top", "#FFFFFF", thickness=2, inset=12),
    EdgeAccentStyle("left", "#FFFFFF", thickness=2, inset=12),
    EdgeAccentStyle("right", "#050813", thickness=3, inset=12),
    EdgeAccentStyle("bottom", "#050813", thickness=3, inset=12),
)

_DEFAULT_STYLE = PanelDepthStyle(
    shadow_layers=(DepthLayerStyle(9, 11, 0, 0, "#070A12", corner_radius=22),),
    edge_accents=_COMMON_EDGE_ACCENTS,
)

_SKIN_DEPTH_STYLES: dict[str, PanelDepthStyle] = {
    "binder": PanelDepthStyle(
        shadow_layers=(DepthLayerStyle(10, 12, 2, 2, "#07040A", corner_radius=22),),
        edge_accents=(
            EdgeAccentStyle("top", "#6B4A32", thickness=3, inset=14),
            EdgeAccentStyle("left", "#7C4A33", thickness=3, inset=14),
            EdgeAccentStyle("right", "#0A0610", thickness=4, inset=14),
            EdgeAccentStyle("bottom", "#0A0610", thickness=4, inset=14),
        ),
        stack_strip_side="right",
        stack_strip_color="#EAD7A2",
        stack_strip_width=9,
    ),
    "dossier": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(
                7,
                9,
                6,
                7,
                "#6B5127",
                border_color="#92713A",
                border_width=1,
                corner_radius=18,
            ),
            DepthLayerStyle(11, 14, 3, 3, "#3D2B14", corner_radius=18),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#D4B875", thickness=3, inset=12),
            EdgeAccentStyle("left", "#C59E4B", thickness=3, inset=12),
            EdgeAccentStyle("right", "#4A3417", thickness=4, inset=12),
            EdgeAccentStyle("bottom", "#3B2A15", thickness=4, inset=12),
        ),
        stack_strip_side="bottom",
        stack_strip_color="#CDAA60",
        stack_strip_width=6,
    ),
    "paper_stack": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(
                6,
                7,
                0,
                0,
                "#F8F2E5",
                border_color="#D7C29A",
                border_width=1,
                corner_radius=18,
            ),
            DepthLayerStyle(
                13,
                15,
                0,
                0,
                "#EADCC2",
                border_color="#CDB58C",
                border_width=1,
                corner_radius=18,
            ),
            DepthLayerStyle(18, 20, 0, 0, "#C7B391", corner_radius=18),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#FFF8E8", thickness=2, inset=14),
            EdgeAccentStyle("left", "#FFF8E8", thickness=2, inset=14),
            EdgeAccentStyle("right", "#C9B893", thickness=3, inset=14),
            EdgeAccentStyle("bottom", "#BCA982", thickness=3, inset=14),
        ),
        stack_strip_side="right",
        stack_strip_color="#D8C6A2",
        stack_strip_width=7,
    ),
    "parchment": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(
                5,
                7,
                0,
                0,
                "#F5E4B8",
                border_color="#D1A85A",
                border_width=1,
                corner_radius=18,
            ),
            DepthLayerStyle(
                12,
                13,
                0,
                0,
                "#D6B16B",
                border_color="#B98224",
                border_width=1,
                corner_radius=18,
            ),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#FFE9B6", thickness=2, inset=14),
            EdgeAccentStyle("left", "#FFE9B6", thickness=2, inset=14),
            EdgeAccentStyle("right", "#9A6A19", thickness=3, inset=14),
            EdgeAccentStyle("bottom", "#8A5A14", thickness=3, inset=14),
        ),
        stack_strip_side="bottom",
        stack_strip_color="#C9973E",
        stack_strip_width=7,
    ),
    "index_cards": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(
                6,
                6,
                0,
                0,
                "#FFFFFF",
                border_color="#CBD5E1",
                border_width=1,
                corner_radius=16,
            ),
            DepthLayerStyle(
                12,
                12,
                0,
                0,
                "#E2E8F0",
                border_color="#CBD5E1",
                border_width=1,
                corner_radius=16,
            ),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#FFFFFF", thickness=2, inset=12),
            EdgeAccentStyle("left", "#FFFFFF", thickness=2, inset=12),
            EdgeAccentStyle("right", "#CBD5E1", thickness=3, inset=12),
            EdgeAccentStyle("bottom", "#CBD5E1", thickness=3, inset=12),
        ),
        stack_strip_side="right",
        stack_strip_color="#CBD5E1",
        stack_strip_width=6,
    ),
    "slate": PanelDepthStyle(
        shadow_layers=(DepthLayerStyle(9, 11, 0, 0, "#06100E", corner_radius=22),),
        edge_accents=(
            EdgeAccentStyle("top", "#3A7A68", thickness=2, inset=12),
            EdgeAccentStyle("left", "#3A7A68", thickness=2, inset=12),
            EdgeAccentStyle("right", "#06100E", thickness=3, inset=12),
            EdgeAccentStyle("bottom", "#06100E", thickness=3, inset=12),
        ),
    ),
}


def resolve_panel_depth_style(skin_name: str) -> PanelDepthStyle:
    """Return decorative depth styling for a resolved panel skin name."""
    return _SKIN_DEPTH_STYLES.get(skin_name, _DEFAULT_STYLE)
