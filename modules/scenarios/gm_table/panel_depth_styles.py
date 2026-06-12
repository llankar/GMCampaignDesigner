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
    EdgeAccentStyle("top", "#26364F", thickness=1, inset=12),
    EdgeAccentStyle("left", "#223149", thickness=1, inset=12),
    EdgeAccentStyle("right", "#070B13", thickness=2, inset=12),
    EdgeAccentStyle("bottom", "#070B13", thickness=2, inset=12),
)

_DEFAULT_STYLE = PanelDepthStyle(
    shadow_layers=(DepthLayerStyle(8, 10, 0, 0, "#050812", corner_radius=22),),
    edge_accents=_COMMON_EDGE_ACCENTS,
)

_SKIN_DEPTH_STYLES: dict[str, PanelDepthStyle] = {
    "binder": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(8, 10, 0, 0, "#050812", corner_radius=22),
            DepthLayerStyle(3, 4, 0, 0, "#0B1220", border_color="#1D2C45", border_width=1, corner_radius=22),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#28405E", thickness=1, inset=12),
            EdgeAccentStyle("left", "#24425E", thickness=1, inset=12),
            EdgeAccentStyle("right", "#07101C", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#07101C", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#38BDF8",
        stack_strip_width=4,
    ),
    "dossier": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(8, 10, 0, 0, "#050812", corner_radius=22),
            DepthLayerStyle(3, 4, 0, 0, "#0E1626", border_color="#26334B", border_width=1, corner_radius=22),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#2C3550", thickness=1, inset=12),
            EdgeAccentStyle("left", "#2B334B", thickness=1, inset=12),
            EdgeAccentStyle("right", "#080D16", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#080D16", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#A78BFA",
        stack_strip_width=4,
    ),
    "paper_stack": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(8, 10, 0, 0, "#050812", corner_radius=22),
            DepthLayerStyle(3, 4, 0, 0, "#0F1828", border_color="#24324A", border_width=1, corner_radius=22),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#253750", thickness=1, inset=12),
            EdgeAccentStyle("left", "#203248", thickness=1, inset=12),
            EdgeAccentStyle("right", "#07101C", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#07101C", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#22D3EE",
        stack_strip_width=4,
    ),
    "parchment": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(8, 10, 0, 0, "#050812", corner_radius=22),
            DepthLayerStyle(3, 4, 0, 0, "#0D1B24", border_color="#224252", border_width=1, corner_radius=22),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#254B58", thickness=1, inset=12),
            EdgeAccentStyle("left", "#244856", thickness=1, inset=12),
            EdgeAccentStyle("right", "#061119", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#061119", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#34D399",
        stack_strip_width=4,
    ),
    "index_cards": PanelDepthStyle(
        shadow_layers=(
            DepthLayerStyle(8, 10, 0, 0, "#050812", corner_radius=22),
            DepthLayerStyle(3, 4, 0, 0, "#101827", border_color="#28364D", border_width=1, corner_radius=22),
        ),
        edge_accents=(
            EdgeAccentStyle("top", "#303B50", thickness=1, inset=12),
            EdgeAccentStyle("left", "#2B3548", thickness=1, inset=12),
            EdgeAccentStyle("right", "#080D16", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#080D16", thickness=2, inset=12),
        ),
        stack_strip_side="left",
        stack_strip_color="#F59E0B",
        stack_strip_width=4,
    ),
    "slate": PanelDepthStyle(
        shadow_layers=(DepthLayerStyle(8, 10, 0, 0, "#04100F", corner_radius=22),),
        edge_accents=(
            EdgeAccentStyle("top", "#27615A", thickness=1, inset=12),
            EdgeAccentStyle("left", "#24564F", thickness=1, inset=12),
            EdgeAccentStyle("right", "#04100F", thickness=2, inset=12),
            EdgeAccentStyle("bottom", "#04100F", thickness=2, inset=12),
        ),
    ),
}


def resolve_panel_depth_style(skin_name: str) -> PanelDepthStyle:
    """Return decorative depth styling for a resolved panel skin name."""
    return _SKIN_DEPTH_STYLES.get(skin_name, _DEFAULT_STYLE)
