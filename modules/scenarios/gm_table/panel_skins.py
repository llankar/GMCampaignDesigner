"""Visual skin definitions for GM Table floating panels."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class PanelSkin:
    """Physical-object skin resolved for a GM Table floating panel."""

    name: str
    body_color: str
    header_color: str
    border_color: str
    accent_color: str
    object_type: str
    icon: str
    show_spine: bool
    show_file_tab: bool
    show_page_edges: bool

    @property
    def label(self) -> str:
        """Return the short header label shown above the panel title."""
        return f"{self.icon} {self.object_type}".strip()

    @property
    def panel_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.body_color

    @property
    def panel_border(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.border_color

    @property
    def panel_focus(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.accent_color

    @property
    def header_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.header_color

    @property
    def header_border(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.accent_color

    @property
    def eyebrow_color(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.accent_color

    @property
    def title_color(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return "#1F2937" if _is_light_color(self.header_color) else "#F4F7FB"

    @property
    def control_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.border_color

    @property
    def control_hover(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.accent_color

    @property
    def control_text(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return "#1F2937" if _is_light_color(self.control_bg) else "#F4F7FB"

    @property
    def close_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return "#7C2D12"

    @property
    def close_hover(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return "#B45309"

    @property
    def resize_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.border_color

    @property
    def resize_text(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.accent_color

    @property
    def border_width(self) -> int:
        """Compatibility alias for existing workspace rendering code."""
        return 2 if self.show_spine or self.show_file_tab else 1

    @property
    def header_border_width(self) -> int:
        """Compatibility alias for existing workspace rendering code."""
        return 1 if self.show_file_tab or self.show_page_edges or self.show_spine else 0


def _is_light_color(color: str) -> bool:
    """Return whether a #RRGGBB color is light enough for dark text."""
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return False
    try:
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
    except ValueError:
        return False
    return (red * 0.299 + green * 0.587 + blue * 0.114) > 186


_PANEL_SKINS: dict[str, PanelSkin] = {
    "binder": PanelSkin(
        name="binder",
        body_color="#14111C",
        header_color="#2A1721",
        border_color="#5B3A2E",
        accent_color="#FBBF24",
        object_type="Campaign Binder",
        icon="📚",
        show_spine=True,
        show_file_tab=False,
        show_page_edges=False,
    ),
    "dossier": PanelSkin(
        name="dossier",
        body_color="#171611",
        header_color="#352812",
        border_color="#8A6F3C",
        accent_color="#FACC15",
        object_type="Dossier",
        icon="🗂",
        show_spine=False,
        show_file_tab=True,
        show_page_edges=False,
    ),
    "paper_stack": PanelSkin(
        name="paper_stack",
        body_color="#F3E8D0",
        header_color="#E8DCC4",
        border_color="#D7C29A",
        accent_color="#B45309",
        object_type="Paper Stack",
        icon="📎",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
    ),
    "parchment": PanelSkin(
        name="parchment",
        body_color="#F1DFAF",
        header_color="#3F2F17",
        border_color="#A16207",
        accent_color="#F59E0B",
        object_type="Map Sheet",
        icon="✍",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
    ),
    "index_cards": PanelSkin(
        name="index_cards",
        body_color="#F8FAFC",
        header_color="#1E293B",
        border_color="#CBD5E1",
        accent_color="#A78BFA",
        object_type="GM Notes",
        icon="✦",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
    ),
    "slate": PanelSkin(
        name="slate",
        body_color="#101816",
        header_color="#17342E",
        border_color="#2F5D50",
        accent_color="#34D399",
        object_type="Slate Board",
        icon="▣",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=False,
    ),
    "default": PanelSkin(
        name="default",
        body_color="#0F1523",
        header_color="#171F30",
        border_color="#34405A",
        accent_color="#7DD3FC",
        object_type="GM Panel",
        icon="",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=False,
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

_KIND_OBJECT_TYPES = {
    "ambiance": "Ambiance Board",
    "character_graph": "Character Graph",
    "note": "GM Note",
    "puzzle_display": "Puzzle Notes",
    "scenario_graph": "Scenario Graph",
}

_ENTITY_SKIN_OVERRIDES: dict[str, PanelSkin] = {
    "NPCs": PanelSkin(
        name="dossier",
        body_color="#171611",
        header_color="#352812",
        border_color="#8A6F3C",
        accent_color="#FACC15",
        object_type="Character Dossier",
        icon="👤",
        show_spine=False,
        show_file_tab=True,
        show_page_edges=False,
    ),
    "PCs": PanelSkin(
        name="dossier",
        body_color="#171611",
        header_color="#352812",
        border_color="#8A6F3C",
        accent_color="#FACC15",
        object_type="Character Dossier",
        icon="⭐",
        show_spine=False,
        show_file_tab=True,
        show_page_edges=False,
    ),
    "Places": PanelSkin(
        name="dossier",
        body_color="#161B22",
        header_color="#29424A",
        border_color="#2F6F7E",
        accent_color="#67E8F9",
        object_type="Location Folder",
        icon="📍",
        show_spine=False,
        show_file_tab=True,
        show_page_edges=False,
    ),
    "Bases": PanelSkin(
        name="dossier",
        body_color="#161B22",
        header_color="#29424A",
        border_color="#2F6F7E",
        accent_color="#67E8F9",
        object_type="Location Folder",
        icon="🏰",
        show_spine=False,
        show_file_tab=True,
        show_page_edges=False,
    ),
    "Clues": PanelSkin(
        name="paper_stack",
        body_color="#F8FAFC",
        header_color="#E8DCC4",
        border_color="#CBD5E1",
        accent_color="#B45309",
        object_type="Evidence Note",
        icon="🔎",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
    ),
    "Informations": PanelSkin(
        name="paper_stack",
        body_color="#F8FAFC",
        header_color="#E8DCC4",
        border_color="#CBD5E1",
        accent_color="#B45309",
        object_type="Evidence Note",
        icon="🧾",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
    ),
    "Objects": PanelSkin(
        name="binder",
        body_color="#14111C",
        header_color="#2A1721",
        border_color="#5B3A2E",
        accent_color="#FBBF24",
        object_type="Inventory Ledger",
        icon="⚖",
        show_spine=True,
        show_file_tab=False,
        show_page_edges=False,
    ),
    "Creatures": PanelSkin(
        name="parchment",
        body_color="#F1DFAF",
        header_color="#3F2F17",
        border_color="#A16207",
        accent_color="#F59E0B",
        object_type="Bestiary Page",
        icon="🐾",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
    ),
    "Scenarios": PanelSkin(
        name="binder",
        body_color="#14111C",
        header_color="#2A1721",
        border_color="#5B3A2E",
        accent_color="#FBBF24",
        object_type="Scenario Dossier",
        icon="📚",
        show_spine=True,
        show_file_tab=False,
        show_page_edges=False,
    ),
}


_ENTITY_TYPE_ALIASES = {
    entity_type.casefold(): entity_type
    for entity_type in _ENTITY_SKIN_OVERRIDES
}
_ENTITY_TYPE_ALIASES.update(
    {
        "base": "Bases",
        "bases": "Bases",
        "clue": "Clues",
        "clues": "Clues",
        "creature": "Creatures",
        "creatures": "Creatures",
        "info": "Informations",
        "information": "Informations",
        "informations": "Informations",
        "npc": "NPCs",
        "npcs": "NPCs",
        "object": "Objects",
        "objects": "Objects",
        "pc": "PCs",
        "pcs": "PCs",
        "place": "Places",
        "places": "Places",
        "scenario": "Scenarios",
        "scenarios": "Scenarios",
    }
)


def _with_object_type(skin: PanelSkin, object_type: str) -> PanelSkin:
    """Return ``skin`` with a different object type while preserving its chrome."""
    return replace(skin, object_type=object_type)


def _entity_type_skin(entity_type: object) -> PanelSkin | None:
    """Return a specialized entity skin for display labels, slugs, or singular names."""
    normalized = str(entity_type or "").strip().replace("_", " ").replace("-", " ").casefold()
    compact = normalized.replace(" ", "")
    canonical = _ENTITY_TYPE_ALIASES.get(normalized) or _ENTITY_TYPE_ALIASES.get(compact)
    if canonical is None:
        return None
    return _ENTITY_SKIN_OVERRIDES[canonical]


def _default_kind_label(kind: str) -> str:
    """Return the same generic kind label the workspace used before skins."""
    if not kind or kind == "entity":
        return ""
    return kind.replace("_", " ").title()


def resolve_panel_skin(kind: str, state: dict | None = None) -> PanelSkin:
    """Resolve the visual skin to use for a panel kind and payload state."""
    normalized_kind = str(kind or "").strip().lower()
    panel_state = state or {}
    if normalized_kind == "entity":
        return _entity_type_skin(panel_state.get("entity_type")) or _PANEL_SKINS["dossier"]

    skin_name = _KIND_TO_SKIN.get(normalized_kind, "default")
    skin = _PANEL_SKINS[skin_name]
    object_type = _KIND_OBJECT_TYPES.get(normalized_kind)
    if object_type:
        return _with_object_type(skin, object_type)
    if skin_name == "default":
        return _with_object_type(skin, _default_kind_label(normalized_kind))
    return skin
