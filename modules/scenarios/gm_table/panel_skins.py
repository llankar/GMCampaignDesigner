"""Visual skin definitions for GM Table floating panels."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class PanelChrome:
    """Resolved non-behavioral chrome values consumed by workspace rendering."""

    panel_bg: str
    panel_border: str
    marker: str = ""


@dataclass(frozen=True, slots=True)
class DeskSpreadAccentVariant:
    """Edge-accent palette applied when panels are spread across the desk."""

    top: str
    left: str
    right: str
    bottom: str


@dataclass(frozen=True, slots=True)
class PanelSkin:
    """Polished tabletop-card skin resolved for a GM Table floating panel."""

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
    header_text_color: str = "#F8FAFC"
    body_text_color: str = "#E5EDF8"
    control_surface: str = "#1D2638"
    control_hover_color: str = "#2B3953"
    close_surface: str = "#272334"
    close_hover_color: str = "#7F1D3A"

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
        return _mix_with_dark(self.accent_color, 0.55)

    @property
    def eyebrow_color(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return _soft_accent(self.accent_color)

    @property
    def title_color(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.header_text_color

    @property
    def control_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.control_surface

    @property
    def control_hover(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.control_hover_color

    @property
    def control_text(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return readable_text_color(self.control_surface)

    @property
    def close_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.close_surface

    @property
    def close_hover(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.close_hover_color

    @property
    def resize_bg(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.control_surface

    @property
    def resize_text(self) -> str:
        """Compatibility alias for existing workspace rendering code."""
        return self.eyebrow_color

    @property
    def border_width(self) -> int:
        """Compatibility alias for existing workspace rendering code."""
        return 1

    @property
    def header_border_width(self) -> int:
        """Compatibility alias for existing workspace rendering code."""
        return 1


def _hex_to_rgb(color: str) -> tuple[int, int, int] | None:
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return None
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return None


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, channel)):02X}" for channel in rgb)


def _mix(color: str, target: str, ratio: float) -> str:
    rgb = _hex_to_rgb(color)
    target_rgb = _hex_to_rgb(target)
    if rgb is None or target_rgb is None:
        return color
    clamped = max(0.0, min(1.0, float(ratio)))
    return _rgb_to_hex(
        tuple(
            int(round(source * (1.0 - clamped) + destination * clamped))
            for source, destination in zip(rgb, target_rgb, strict=True)
        )
    )


def _mix_with_dark(color: str, ratio: float) -> str:
    return _mix(color, "#0B1020", ratio)


def _soft_accent(color: str) -> str:
    return _mix(color, "#F8FAFC", 0.18)


def _is_light_color(color: str) -> bool:
    """Return whether a #RRGGBB color is light enough for dark text."""
    rgb = _hex_to_rgb(color)
    if rgb is None:
        return False
    red, green, blue = rgb
    return (red * 0.299 + green * 0.587 + blue * 0.114) > 186


def readable_text_color(color: str, *, dark: str = "#111827", light: str = "#F8FAFC") -> str:
    """Return a readable foreground for a solid ``#RRGGBB`` background."""
    return dark if _is_light_color(color) else light


_PANEL_SKINS: dict[str, PanelSkin] = {
    # Fleet Admiral — deep midnight navy with electric cyan.
    # Evokes a high-security intelligence briefing binder.
    "binder": PanelSkin(
        name="binder",
        body_color="#0B1428",
        header_color="#0F1E3A",
        border_color="#1B3565",
        accent_color="#22D4FF",
        object_type="Campaign Dossier",
        icon="📚",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=False,
        control_surface="#142240",
        control_hover_color="#1F3560",
    ),
    # Shadow Archive — deep indigo-black with vivid violet.
    # Evokes mysterious character files kept under lock and key.
    "dossier": PanelSkin(
        name="dossier",
        body_color="#0D0F20",
        header_color="#141628",
        border_color="#2C2E70",
        accent_color="#A855F7",
        object_type="Dossier",
        icon="🗂",
        show_spine=False,
        show_file_tab=True,
        show_page_edges=False,
        control_surface="#1C1E3C",
        control_hover_color="#2E3062",
    ),
    # Obsidian Archive — cold dark slate with vivid sky blue.
    # Evokes a stack of classified documents in low light.
    "paper_stack": PanelSkin(
        name="paper_stack",
        body_color="#0A1422",
        header_color="#0D1A2E",
        border_color="#1A3254",
        accent_color="#0EB4E7",
        object_type="Handout Deck",
        icon="📎",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
        control_surface="#122230",
        control_hover_color="#1C3450",
    ),
    # Forest Cartographer — dark forest teal with vivid emerald.
    # Evokes an explorer's map unrolled on a woodland table.
    "parchment": PanelSkin(
        name="parchment",
        body_color="#091A14",
        header_color="#0D2A1E",
        border_color="#165C3A",
        accent_color="#10C97C",
        object_type="Map Sheet",
        icon="✍",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
        control_surface="#122820",
        control_hover_color="#1C3C30",
    ),
    # Inkmaster Archive — deep midnight ink with warm amber accent strip.
    # Evokes a scholar's inked note cards lit by candlelight.
    "index_cards": PanelSkin(
        name="index_cards",
        body_color="#0D1526",
        header_color="#121E38",
        border_color="#1E3458",
        accent_color="#60A5FA",
        object_type="GM Notes",
        icon="✦",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=True,
        control_surface="#182030",
        control_hover_color="#263548",
    ),
    # Obsidian Codex — near-black with vivid teal luminescence.
    # Evokes a dark chalkboard glowing faintly in a dim chamber.
    "slate": PanelSkin(
        name="slate",
        body_color="#090E12",
        header_color="#0D1C1A",
        border_color="#154035",
        accent_color="#14C4AE",
        object_type="Slate Board",
        icon="▣",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=False,
        control_surface="#102020",
        control_hover_color="#1A3430",
    ),
    "default": PanelSkin(
        name="default",
        body_color="#0C1422",
        header_color="#111E30",
        border_color="#2A3852",
        accent_color="#7DD3FC",
        object_type="GM Panel",
        icon="",
        show_spine=False,
        show_file_tab=False,
        show_page_edges=False,
    ),
}

_PANEL_CHROME: dict[str, PanelChrome] = {
    "paper_stack": PanelChrome(panel_bg="#0A1422", panel_border="#1A3254", marker="HANDOUT"),
    "parchment": PanelChrome(panel_bg="#091A14", panel_border="#165C3A", marker="MAP"),
    "index_cards": PanelChrome(panel_bg="#0D1526", panel_border="#1E3458", marker="NOTE"),
}

DESK_SPREAD_ACCENT_VARIANTS: tuple[DeskSpreadAccentVariant, ...] = (
    DeskSpreadAccentVariant("#44DFFF", "#22D4FF", "#0E4B65", "#063344"),
    DeskSpreadAccentVariant("#C084FC", "#A855F7", "#4C1A8A", "#2E1065"),
    DeskSpreadAccentVariant("#34E890", "#10C97C", "#065C3A", "#022C1E"),
    DeskSpreadAccentVariant("#93C5FD", "#60A5FA", "#1E3A8A", "#172554"),
    DeskSpreadAccentVariant("#CBD5E1", "#94A3B8", "#334155", "#0F172A"),
    DeskSpreadAccentVariant("#5EEAD4", "#14C4AE", "#115E52", "#042F2C"),
)


def resolve_panel_chrome(skin: PanelSkin) -> PanelChrome:
    """Return workspace chrome colors and marker text for a resolved panel skin."""
    return _PANEL_CHROME.get(
        skin.name,
        PanelChrome(panel_bg=skin.panel_bg, panel_border=skin.panel_border, marker=skin.icon),
    )

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
    "NPCs": replace(_PANEL_SKINS["dossier"], object_type="Character Dossier", icon="👤"),
    "PCs": replace(_PANEL_SKINS["dossier"], object_type="Character Dossier", icon="⭐"),
    "Places": replace(
        _PANEL_SKINS["dossier"],
        border_color="#1A5A70",
        accent_color="#22D4FF",
        object_type="Location Dossier",
        icon="📍",
    ),
    "Bases": replace(
        _PANEL_SKINS["dossier"],
        border_color="#1A5A70",
        accent_color="#22D4FF",
        object_type="Location Dossier",
        icon="🏰",
    ),
    "Clues": replace(_PANEL_SKINS["paper_stack"], object_type="Evidence Card", icon="🔎"),
    "Informations": replace(_PANEL_SKINS["paper_stack"], object_type="Evidence Card", icon="🧾"),
    "Objects": replace(_PANEL_SKINS["binder"], object_type="Inventory Ledger", icon="⚖"),
    "Creatures": replace(_PANEL_SKINS["parchment"], object_type="Bestiary Card", icon="🐾"),
    "Scenarios": replace(_PANEL_SKINS["binder"], object_type="Scenario Dossier", icon="📚"),
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
