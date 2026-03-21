from __future__ import annotations

from dataclasses import dataclass

from modules.helpers import theme_manager


@dataclass(slots=True)
class MenuLayoutMetrics:
    mode: str
    menu_button_padx: tuple[int, int]
    menu_button_pady: int
    quick_button_padx: int
    quick_button_pady: int
    action_group_padx: tuple[int, int]
    frame_padding: tuple[int, int]
    quick_inner_pady: int
    system_group_padx: tuple[int, int]


class MenuLayoutController:
    """Compute responsive menu spacing without leaking layout rules to MainWindow."""

    COMPACT_BREAKPOINT = 1360

    @classmethod
    def resolve(cls, width: int) -> MenuLayoutMetrics:
        if width <= cls.COMPACT_BREAKPOINT:
            return MenuLayoutMetrics(
                mode="compact",
                menu_button_padx=(0, 2),
                menu_button_pady=1,
                quick_button_padx=2,
                quick_button_pady=1,
                action_group_padx=(4, 6),
                frame_padding=(0, 4),
                quick_inner_pady=1,
                system_group_padx=(0, 6),
            )
        return MenuLayoutMetrics(
            mode="expanded",
            menu_button_padx=(0, 6),
            menu_button_pady=2,
            quick_button_padx=5,
            quick_button_pady=2,
            action_group_padx=(6, 10),
            frame_padding=(0, 8),
            quick_inner_pady=2,
            system_group_padx=(0, 8),
        )


@dataclass(slots=True)
class MenuVisualPalette:
    menu_bg: str
    panel_bg: str
    button_fg: str
    button_hover: str
    button_border: str
    text_color: str
    muted_text_color: str
    divider_color: str
    shadow_color: str
    active_bg: str
    active_border: str
    active_text: str
    focus_ring: str
    focus_glow: str
    accent_hover: str
    system_fg: str
    system_hover: str
    system_border: str
    system_text: str

    @classmethod
    def from_theme(cls, theme: str | None = None) -> "MenuVisualPalette":
        tokens = theme_manager.get_tokens(theme)
        menu_bg = tokens.get("sidebar_header_bg", tokens.get("panel_alt_bg", "#132133"))
        button_fg = tokens.get("button_fg", "#0077CC")
        panel_bg = tokens.get("panel_bg", menu_bg)
        button_hover = tokens.get("button_hover", button_fg)
        button_border = tokens.get("button_border", button_hover)
        accent_hover = tokens.get("accent_button_hover", "#2497FF")
        divider_color = tokens.get("menu_divider", button_border)
        shadow_color = tokens.get("menu_shadow", panel_bg)
        return cls(
            menu_bg=menu_bg,
            panel_bg=panel_bg,
            button_fg=button_fg,
            button_hover=button_hover,
            button_border=button_border,
            text_color="#E8EEF6",
            muted_text_color=tokens.get("muted_text_color", "#8FA4BA"),
            divider_color=divider_color,
            shadow_color=shadow_color,
            active_bg=button_fg,
            active_border=button_border,
            active_text="#FFFFFF",
            focus_ring=button_border,
            focus_glow=accent_hover,
            accent_hover=accent_hover,
            system_fg="#53361F",
            system_hover="#7A4D28",
            system_border="#B77A3A",
            system_text="#FFE7C2",
        )
