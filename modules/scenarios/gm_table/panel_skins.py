"""Visual skin definitions for GM Table floating panels."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class PanelSkin:
    """Chrome colors and labels used to render a GM Table panel."""

    name: str
    label: str
    panel_bg: str
    panel_border: str
    panel_focus: str
    header_bg: str
    header_border: str
    eyebrow_color: str
    title_color: str
    control_bg: str
    control_hover: str
    control_text: str
    close_bg: str
    close_hover: str
    resize_bg: str
    resize_text: str
    border_width: int = 1
    header_border_width: int = 0


_PANEL_SKINS: dict[str, PanelSkin] = {
    "binder": PanelSkin(
        name="binder",
        label="Campaign Binder",
        panel_bg="#14111C",
        panel_border="#5B3A2E",
        panel_focus="#FBBF24",
        header_bg="#2A1721",
        header_border="#8B5A2B",
        eyebrow_color="#FCD34D",
        title_color="#FFF7ED",
        control_bg="#3A2430",
        control_hover="#4A2D3C",
        control_text="#FFF7ED",
        close_bg="#5B2A1E",
        close_hover="#7C2D12",
        resize_bg="#3A2430",
        resize_text="#FCD34D",
        border_width=2,
        header_border_width=1,
    ),
    "dossier": PanelSkin(
        name="dossier",
        label="Dossier",
        panel_bg="#171611",
        panel_border="#8A6F3C",
        panel_focus="#FACC15",
        header_bg="#352812",
        header_border="#B0893C",
        eyebrow_color="#FDE68A",
        title_color="#FFF7D6",
        control_bg="#4A391B",
        control_hover="#5C4722",
        control_text="#FFF7D6",
        close_bg="#6A321A",
        close_hover="#8A3E1A",
        resize_bg="#4A391B",
        resize_text="#FDE68A",
        border_width=2,
        header_border_width=1,
    ),
    "paper_stack": PanelSkin(
        name="paper_stack",
        label="Paper Stack",
        panel_bg="#161B22",
        panel_border="#CBD5E1",
        panel_focus="#60A5FA",
        header_bg="#E8DCC4",
        header_border="#BFAF91",
        eyebrow_color="#7C2D12",
        title_color="#1F2937",
        control_bg="#BFAF91",
        control_hover="#A99773",
        control_text="#1F2937",
        close_bg="#B45309",
        close_hover="#92400E",
        resize_bg="#BFAF91",
        resize_text="#1F2937",
        border_width=2,
        header_border_width=1,
    ),
    "parchment": PanelSkin(
        name="parchment",
        label="Map Sheet",
        panel_bg="#16130D",
        panel_border="#A16207",
        panel_focus="#F59E0B",
        header_bg="#3F2F17",
        header_border="#D97706",
        eyebrow_color="#FCD34D",
        title_color="#FEF3C7",
        control_bg="#5A3D18",
        control_hover="#744D1E",
        control_text="#FEF3C7",
        close_bg="#7C2D12",
        close_hover="#9A3412",
        resize_bg="#5A3D18",
        resize_text="#FCD34D",
        border_width=2,
        header_border_width=1,
    ),
    "index_cards": PanelSkin(
        name="index_cards",
        label="GM Notes",
        panel_bg="#111827",
        panel_border="#475569",
        panel_focus="#A78BFA",
        header_bg="#1E293B",
        header_border="#64748B",
        eyebrow_color="#C4B5FD",
        title_color="#F8FAFC",
        control_bg="#334155",
        control_hover="#475569",
        control_text="#F8FAFC",
        close_bg="#4C1D95",
        close_hover="#5B21B6",
        resize_bg="#334155",
        resize_text="#C4B5FD",
        border_width=1,
        header_border_width=1,
    ),
    "slate": PanelSkin(
        name="slate",
        label="Slate Board",
        panel_bg="#101816",
        panel_border="#2F5D50",
        panel_focus="#34D399",
        header_bg="#17342E",
        header_border="#3A7A68",
        eyebrow_color="#A7F3D0",
        title_color="#ECFDF5",
        control_bg="#235347",
        control_hover="#2F6F5F",
        control_text="#ECFDF5",
        close_bg="#7F1D1D",
        close_hover="#991B1B",
        resize_bg="#235347",
        resize_text="#A7F3D0",
        border_width=2,
        header_border_width=1,
    ),
    "default": PanelSkin(
        name="default",
        label="GM Panel",
        panel_bg="#0F1523",
        panel_border="#34405A",
        panel_focus="#7DD3FC",
        header_bg="#171F30",
        header_border="#34405A",
        eyebrow_color="#F59E0B",
        title_color="#F4F7FB",
        control_bg="#20283A",
        control_hover="#283146",
        control_text="#F4F7FB",
        close_bg="#453116",
        close_hover="#5B3414",
        resize_bg="#20283A",
        resize_text="#9EABC2",
        border_width=1,
        header_border_width=0,
    ),
}

_KIND_TO_SKIN = {
    "scenario": "binder",
    "campaign_dashboard": "binder",
    "scene_flow": "binder",
    "entity": "dossier",
    "handouts": "paper_stack",
    "image_library": "paper_stack",
    "world_map": "parchment",
    "map_tool": "parchment",
    "random_tables": "index_cards",
    "plot_twists": "index_cards",
    "loot_generator": "index_cards",
    "note": "index_cards",
    "puzzle_display": "index_cards",
    "whiteboard": "slate",
    "ambiance": "slate",
    "character_graph": "slate",
    "scenario_graph": "slate",
}

_KIND_LABELS = {
    "ambiance": "Ambiance Board",
    "character_graph": "Character Graph",
    "note": "GM Note",
    "puzzle_display": "Puzzle Notes",
    "scenario_graph": "Scenario Graph",
}

_ENTITY_LABELS = {
    "Scenarios": "Scenario Dossier",
    "Informations": "Info Dossier",
    "Places": "Place Dossier",
    "Bases": "Base Dossier",
    "Objects": "Object Dossier",
    "Creatures": "Creature Dossier",
}


def _default_kind_label(kind: str) -> str:
    """Return the same generic kind label the workspace used before skins."""
    if not kind or kind == "entity":
        return ""
    return kind.replace("_", " ").title()


def _label_for_kind(kind: str, state: dict, *, skin_name: str) -> str | None:
    """Return a user-facing skin label override for a panel kind."""
    if kind == "entity":
        entity_type = str(state.get("entity_type") or "").strip()
        return _ENTITY_LABELS.get(entity_type)
    if kind in _KIND_LABELS:
        return _KIND_LABELS[kind]
    if skin_name == "default":
        return _default_kind_label(kind)
    return None


def resolve_panel_skin(kind: str, state: dict | None = None) -> PanelSkin:
    """Resolve the visual skin to use for a panel kind and payload state."""
    normalized_kind = str(kind or "").strip().lower()
    skin_name = _KIND_TO_SKIN.get(normalized_kind, "default")
    skin = _PANEL_SKINS[skin_name]
    label = _label_for_kind(normalized_kind, state or {}, skin_name=skin_name)
    if label is None or label == skin.label:
        return skin
    return replace(skin, label=label)
