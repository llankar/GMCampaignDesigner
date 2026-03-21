from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk

from modules.ui.menu.menu_visual_state import MenuLayoutMetrics, MenuVisualPalette


@dataclass(slots=True)
class MenuChromeOptions:
    show_divider: bool = True
    show_shadow: bool = True


class MenuChrome:
    def __init__(self, parent, *, options: MenuChromeOptions | None = None):
        self.options = options or MenuChromeOptions()
        self.container = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        self.divider = ctk.CTkFrame(self.container, height=1, corner_radius=0)
        self.shadow = ctk.CTkFrame(self.container, height=1, corner_radius=0)
        if self.options.show_divider:
            self.divider.pack(fill="x")
        if self.options.show_shadow:
            self.shadow.pack(fill="x")

    def pack(self, **kwargs):
        self.container.pack(**kwargs)

    def apply_theme(self, palette: MenuVisualPalette):
        self.container.configure(fg_color="transparent")
        if self.options.show_divider:
            self.divider.configure(fg_color=palette.divider_color)
        if self.options.show_shadow:
            self.shadow.configure(fg_color=palette.shadow_color)


class TopLevelMenuButton:
    def __init__(self, parent, *, label: str, command: Callable[[], None], width: int, height: int, font, corner_radius: int = 9):
        self.label = label
        self.button = ctk.CTkButton(
            parent,
            text=label,
            width=width,
            height=height,
            corner_radius=corner_radius,
            border_width=1,
            command=command,
        )
        self.is_open = False
        self.is_active = False
        self._last_palette: MenuVisualPalette | None = None

    def pack(self, **kwargs):
        self.button.pack(**kwargs)

    def set_open(self, is_open: bool):
        self.is_open = is_open
        if is_open:
            self.is_active = True
        self.apply_theme(self._last_palette)

    def set_active(self, is_active: bool):
        self.is_active = is_active
        self.apply_theme(self._last_palette)

    def apply_theme(self, palette: MenuVisualPalette | None, *, width: int | None = None):
        if palette is None:
            return
        self._last_palette = palette
        fg_color = palette.active_bg if self.is_open or self.is_active else palette.menu_bg
        text_color = palette.active_text if self.is_open else palette.text_color
        border_color = palette.active_border if self.is_open or self.is_active else palette.menu_bg
        hover_color = palette.active_bg if self.is_open else palette.button_fg
        updates = {
            "fg_color": fg_color,
            "hover_color": hover_color,
            "text_color": text_color,
            "border_color": border_color,
            "border_width": 1,
        }
        if width is not None:
            updates["width"] = width
        self.button.configure(**updates)


class QuickActionButton:
    def __init__(self, parent, *, text: str, image, command: Callable[[], None], style: str, width: int, height: int, corner_radius: int, font, border_spacing: int):
        self.style = style
        self.button = ctk.CTkButton(
            parent,
            text=text,
            image=image,
            compound="left",
            anchor="w",
            height=height,
            width=width,
            corner_radius=corner_radius,
            command=command,
            font=font,
            border_spacing=border_spacing,
            border_width=1,
        )
        self.is_focused = False
        self._last_palette: MenuVisualPalette | None = None
        try:
            self.button.configure(takefocus=True)
        except Exception:
            pass
        try:
            self.button.bind("<FocusIn>", self._on_focus_in, add="+")
            self.button.bind("<FocusOut>", self._on_focus_out, add="+")
            self.button.bind("<Button-1>", self._on_pointer_focus, add="+")
        except Exception:
            pass

    def _on_focus_in(self, _event=None):
        self.set_focused(True)

    def _on_focus_out(self, _event=None):
        self.set_focused(False)

    def pack(self, **kwargs):
        self.button.pack(**kwargs)

    def set_focused(self, is_focused: bool):
        self.is_focused = is_focused
        self.apply_theme(self._last_palette)

    def apply_theme(self, palette: MenuVisualPalette | None):
        if palette is None:
            return
        self._last_palette = palette
        base = {
            "primary": {"fg_color": palette.panel_bg, "hover_color": palette.button_fg, "text_color": palette.text_color, "border_color": palette.button_fg},
            "accent": {"fg_color": palette.button_fg, "hover_color": palette.accent_hover, "text_color": palette.active_text, "border_color": palette.button_fg},
            "system": {"fg_color": palette.system_fg, "hover_color": palette.system_hover, "text_color": palette.system_text, "border_color": palette.system_border},
        }.get(self.style, {"fg_color": palette.menu_bg, "hover_color": palette.button_fg, "text_color": palette.muted_text_color, "border_color": palette.button_border})
        if self.is_focused:
            base = {
                **base,
                "border_color": palette.focus_ring,
                "hover_color": palette.focus_glow,
            }
        self.button.configure(**base, border_width=1)


class MenuBarLayoutApplier:
    @staticmethod
    def apply(menu_controllers: list[TopLevelMenuButton], primary_quick: list[QuickActionButton], system_quick: list[QuickActionButton], *, menu_frame, quick_actions_inner, actions_frame, system_quick_frame, utility_actions_frame, metrics: MenuLayoutMetrics):
        menu_frame.grid_configure(padx=metrics.frame_padding)
        quick_actions_inner.pack_configure(pady=metrics.quick_inner_pady)
        actions_frame.grid_configure(padx=metrics.action_group_padx)
        system_quick_frame.pack_configure(padx=metrics.system_group_padx, pady=metrics.quick_inner_pady)
        utility_actions_frame.pack_configure(pady=metrics.quick_inner_pady)
        for controller in menu_controllers:
            controller.button.pack_configure(padx=metrics.menu_button_padx, pady=metrics.menu_button_pady)
        for controller in [*primary_quick, *system_quick]:
            controller.button.pack_configure(padx=metrics.quick_button_padx, pady=metrics.quick_button_pady)
