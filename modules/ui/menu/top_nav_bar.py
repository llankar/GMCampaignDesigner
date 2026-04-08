"""Utilities for menu top nav bar."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from modules.helpers import theme_manager
from modules.ui.menu.menu_image_adapter import prepare_menu_image, resize_ctk_icon
from modules.ui.menu.menu_sections import build_menu_specs, format_menu_label
from modules.ui.menu.quick_actions import (
    build_navigation_quick_actions,
    build_primary_quick_actions,
    build_system_quick_actions,
)


class AppMenuBar:
    """Custom in-window navigation bar with grouped menus and quick actions."""

    FRAME_HEIGHT = 18
    MENU_BUTTON_HEIGHT = 16
    MENU_BUTTON_WIDTH = 70
    BUTTON_FONT = ("Segoe UI", 14)
    MENU_ICON_SIZE = (30, 30)
    QUICK_ICON_SIZE = (16, 16)
    QUICK_BUTTON_HEIGHT = 16
    QUICK_BUTTON_RADIUS = 8
    QUICK_BUTTON_MIN_WIDTH = 64
    QUICK_BUTTON_WIDTH_SCALE = 7

    @staticmethod
    def _normalize_hex(color: str | None, fallback: str) -> str:
        """Normalize hex."""
        value = (color or "").strip()
        if value.startswith("#") and len(value) == 7:
            return value
        return fallback

    @classmethod
    def _mix_colors(cls, first: str | None, second: str | None, ratio: float, *, fallback: str) -> str:
        """Internal helper for mix colors."""
        start = cls._normalize_hex(first, fallback)
        end = cls._normalize_hex(second, fallback)
        weight = max(0.0, min(1.0, ratio))

        def _to_rgb(hex_color: str) -> tuple[int, int, int]:
            """Internal helper for to RGB."""
            return tuple(int(hex_color[index:index + 2], 16) for index in (1, 3, 5))

        rgb_a = _to_rgb(start)
        rgb_b = _to_rgb(end)
        blended = tuple(
            round((1.0 - weight) * component_a + weight * component_b)
            for component_a, component_b in zip(rgb_a, rgb_b)
        )
        return "#{:02x}{:02x}{:02x}".format(*blended)

    def __init__(self, app):
        """Initialize the AppMenuBar instance."""
        self.app = app
        self._root_menu = tk.Menu(app)
        self._submenus: list[tk.Menu] = []
        self._menu_buttons: list[ctk.CTkButton] = []
        self._button_menus: list[tuple[ctk.CTkButton, tk.Menu]] = []
        self._open_menu: tk.Menu | None = None
        self._menu_images: list[tk.PhotoImage] = []
        self._action_buttons: list[ctk.CTkButton] = []
        self._navigation_quick_buttons: dict[str, ctk.CTkButton] = {}
        self._primary_quick_buttons: list[ctk.CTkButton] = []
        self._system_quick_buttons: list[ctk.CTkButton] = []

        self.frame = ctk.CTkFrame(app, corner_radius=0, height=self.FRAME_HEIGHT)
        self.frame.grid_columnconfigure(0, weight=0)
        self.frame.grid_columnconfigure(1, weight=1)
        self.frame.grid_columnconfigure(2, weight=0)

        self.menu_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.quick_actions_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.quick_actions_inner = ctk.CTkFrame(self.quick_actions_frame, fg_color="transparent")
        self.actions_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.system_quick_frame = ctk.CTkFrame(self.actions_frame, fg_color="transparent")
        self.utility_actions_frame = ctk.CTkFrame(self.actions_frame, fg_color="transparent")

        self.menu_frame.grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.quick_actions_frame.grid(row=0, column=1, sticky="ew")
        self.quick_actions_inner.pack(anchor="center", pady=1)
        self.actions_frame.grid(row=0, column=2, sticky="e", padx=(4, 8))
        self.system_quick_frame.pack(side="left", padx=(0, 8), pady=1)
        self.utility_actions_frame.pack(side="right", pady=1)

        self._build()
        self.refresh_theme()

    def _apply_menu_theme(self, menu_widget: tk.Menu):
        """Apply menu theme."""
        tokens = theme_manager.get_tokens()
        menu_fg = "#E8EEF6"
        menu_bg = tokens.get("sidebar_header_bg", tokens.get("panel_alt_bg", "#132133"))
        active_bg = tokens.get("button_fg", "#0077CC")
        active_fg = "#FFFFFF"
        disabled_fg = tokens.get("muted_text_color", "#8FA4BA")

        self.app.option_add("*Menu.background", menu_bg)
        self.app.option_add("*Menu.foreground", menu_fg)
        self.app.option_add("*Menu.activeBackground", active_bg)
        self.app.option_add("*Menu.activeForeground", active_fg)
        self.app.option_add("*Menu.disabledForeground", disabled_fg)

        menu_widget.configure(
            bg=menu_bg,
            fg=menu_fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            disabledforeground=disabled_fg,
            selectcolor=active_bg,
            font=("Segoe UI", 10),
            borderwidth=0,
            tearoff=0,
        )

    def _clear_widgets(self):
        """Clear widgets."""
        for button in [
            *self._menu_buttons,
            *self._action_buttons,
            *self._navigation_quick_buttons.values(),
            *self._primary_quick_buttons,
            *self._system_quick_buttons,
        ]:
            try:
                button.destroy()
            except Exception:
                pass
        self._submenus.clear()
        self._menu_buttons.clear()
        self._button_menus.clear()
        self._menu_images.clear()
        self._action_buttons.clear()
        self._navigation_quick_buttons.clear()
        self._primary_quick_buttons.clear()
        self._system_quick_buttons.clear()

    def _build(self):
        """Build the operation."""
        self._clear_widgets()
        for menu_spec in build_menu_specs(self.app):
            submenu = self._new_submenu()
            self._populate_submenu(submenu, menu_spec)
            self._add_menu_button(menu_spec.label, submenu)
        self._build_quick_actions()

    def rebuild(self):
        """Handle rebuild."""
        self._build()
        self.refresh_theme()

    def _new_submenu(self) -> tk.Menu:
        """Internal helper for new submenu."""
        submenu = tk.Menu(self._root_menu, tearoff=0)
        self._apply_menu_theme(submenu)
        self._submenus.append(submenu)
        return submenu

    def _populate_submenu(self, submenu: tk.Menu, menu_spec):
        """Internal helper for populate submenu."""
        for group_index, group in enumerate(menu_spec.groups):
            # Process each (group_index, group) from enumerate(menu_spec.groups).
            submenu.add_command(label=group.title.upper(), state="disabled")
            submenu.add_command(label=f"  {group.helper}", state="disabled")
            for item in group.items:
                # Process each item from group.items.
                kwargs = {
                    "label": format_menu_label(item),
                    "command": item.command,
                }
                compact_icon = resize_ctk_icon(self._get_icon(item.icon_key), self.MENU_ICON_SIZE)
                icon = prepare_menu_image(compact_icon)
                if icon is not None:
                    self._menu_images.append(icon)
                    kwargs["image"] = icon
                    kwargs["compound"] = "left"
                submenu.add_command(**kwargs)
            if group_index != len(menu_spec.groups) - 1:
                submenu.add_separator()

    def _popup_menu(self, menu: tk.Menu, button: ctk.CTkButton):
        """Internal helper for popup menu."""
        if self._open_menu is not None:
            try:
                self._open_menu.unpost()
            except Exception:
                pass
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            # Keep popup menu resilient if this step fails.
            menu.post(x, y)
            self._open_menu = menu
        finally:
            menu.grab_release()

    def _on_root_click(self, event):
        """Handle root click."""
        if self._open_menu is None:
            return
        widget = event.widget
        for button, _menu in self._button_menus:
            if widget is button:
                return
        try:
            self._open_menu.unpost()
        except Exception:
            pass
        self._open_menu = None

    def _add_menu_button(self, label: str, menu: tk.Menu):
        """Internal helper for add menu button."""
        button = ctk.CTkButton(
            self.menu_frame,
            text=label,
            width=self.MENU_BUTTON_WIDTH,
            height=self.MENU_BUTTON_HEIGHT,
            corner_radius=9,
            border_width=0,
            command=None,
        )
        button.configure(command=lambda m=menu, b=button: self._popup_menu(m, b))
        button.pack(side="left", padx=(0, 4), pady=1)
        self._menu_buttons.append(button)
        self._button_menus.append((button, menu))

    def _build_quick_actions(self):
        """Build quick actions."""
        for action in build_navigation_quick_actions(self.app):
            button = self._create_quick_action_button(self.system_quick_frame, action)
            button.pack(side="left", padx=4)
            self._navigation_quick_buttons[action.text.lower()] = button
        for action in build_primary_quick_actions(self.app):
            button = self._create_quick_action_button(self.quick_actions_inner, action)
            button.pack(side="left", padx=4)
            self._primary_quick_buttons.append(button)
        for action in build_system_quick_actions(self.app):
            button = self._create_quick_action_button(self.system_quick_frame, action)
            button.pack(side="left", padx=4)
            self._system_quick_buttons.append(button)
        self.set_navigation_state(can_go_back=False, can_go_forward=False)

    def set_navigation_state(self, *, can_go_back: bool, can_go_forward: bool):
        """Update quick navigation button states."""
        nav_state = {
            "back": "normal" if can_go_back else "disabled",
            "forward": "normal" if can_go_forward else "disabled",
        }
        for key, state in nav_state.items():
            button = self._navigation_quick_buttons.get(key)
            if button is not None:
                button.configure(state=state)

    def _create_quick_action_button(self, parent, action_spec):
        """Create quick action button."""
        icon = resize_ctk_icon(self._get_icon(action_spec.icon_key), self.QUICK_ICON_SIZE)
        button = ctk.CTkButton(
            parent,
            text=action_spec.text,
            image=icon,
            compound="left",
            anchor="w",
            height=self.QUICK_BUTTON_HEIGHT,
            width=max(self.QUICK_BUTTON_MIN_WIDTH, len(action_spec.text) * self.QUICK_BUTTON_WIDTH_SCALE + 18),
            corner_radius=self.QUICK_BUTTON_RADIUS,
            command=action_spec.command,
            font=self.BUTTON_FONT,
            border_spacing=4,
        )
        button._menu_style = action_spec.style
        return button

    def _get_icon(self, icon_key: str | None):
        """Return icon."""
        return getattr(self.app, "icons", {}).get(icon_key) if icon_key else None

    def attach(self):
        """Handle attach."""
        self.app.configure(menu="")
        self.frame.pack(side="top", fill="x", before=getattr(self.app, "main_frame", None))
        self.app.bind_all("<Button-1>", self._on_root_click, add="+")

    def create_action_button(self, **kwargs) -> ctk.CTkButton:
        """Create action button."""
        kwargs.setdefault("font", self.BUTTON_FONT)
        button = ctk.CTkButton(self.utility_actions_frame, height=16, corner_radius=8, **kwargs)
        button.pack(side="right", padx=(6, 0))
        self._action_buttons.append(button)
        return button

    def refresh_theme(self):
        """Refresh theme."""
        tokens = theme_manager.get_tokens()
        menu_bg = tokens.get("sidebar_header_bg", tokens.get("panel_alt_bg", "#132133"))
        button_fg = tokens.get("button_fg", "#0077CC")
        panel_bg = tokens.get("panel_bg", menu_bg)
        muted_fg = tokens.get("muted_text_color", "#8FA4BA")

        self.frame.configure(fg_color=menu_bg)
        self.menu_frame.configure(fg_color="transparent")
        self.quick_actions_frame.configure(fg_color="transparent")
        self.quick_actions_inner.configure(fg_color="transparent")
        self.actions_frame.configure(fg_color="transparent")
        self.system_quick_frame.configure(fg_color="transparent")
        self.utility_actions_frame.configure(fg_color="transparent")

        for button in self._menu_buttons:
            try:
                # Keep theme resilient if this step fails.
                button.configure(
                    fg_color=menu_bg,
                    hover_color=button_fg,
                    text_color="#E8EEF6",
                    font=self.BUTTON_FONT,
                    width=max(64, len(button.cget("text")) * 11),
                )
            except Exception:
                pass

        for submenu in self._submenus:
            try:
                self._apply_menu_theme(submenu)
            except Exception:
                pass

        for button in self._primary_quick_buttons:
            self._style_quick_button(button, menu_bg=menu_bg, button_fg=button_fg, panel_bg=panel_bg, muted_fg=muted_fg)
        for button in self._system_quick_buttons:
            self._style_quick_button(button, menu_bg=menu_bg, button_fg=button_fg, panel_bg=panel_bg, muted_fg=muted_fg)
        for button in self._navigation_quick_buttons.values():
            self._style_quick_button(button, menu_bg=menu_bg, button_fg=button_fg, panel_bg=panel_bg, muted_fg=muted_fg)

        for button in self._action_buttons:
            try:
                # Keep theme resilient if this step fails.
                if button.cget("fg_color") in ("", "transparent"):
                    button.configure(fg_color=menu_bg)
                if button.cget("hover_color") in ("", "transparent"):
                    button.configure(hover_color=button_fg)
                if button.cget("text_color") in ("", "transparent"):
                    button.configure(text_color="#E8EEF6")
            except Exception:
                pass

    def _style_quick_button(self, button, *, menu_bg: str, button_fg: str, panel_bg: str, muted_fg: str):
        """Internal helper for style quick button."""
        accent_fg = theme_manager.get_tokens().get("accent_button_fg", button_fg)
        accent_hover = theme_manager.get_tokens().get("accent_button_hover", button_fg)
        subtle_fg = self._mix_colors(menu_bg, panel_bg, 0.25, fallback=menu_bg)
        subtle_hover = self._mix_colors(menu_bg, button_fg, 0.35, fallback=button_fg)
        accent_bg = self._mix_colors(menu_bg, accent_fg, 0.45, fallback=accent_fg)
        accent_hover_bg = self._mix_colors(button_fg, accent_hover, 0.5, fallback=button_fg)
        system_bg = self._mix_colors(menu_bg, accent_fg, 0.22, fallback=menu_bg)
        system_hover = self._mix_colors(button_fg, accent_hover, 0.25, fallback=button_fg)

        palette = {
            "primary": {
                "fg_color": subtle_fg,
                "hover_color": subtle_hover,
                "text_color": "#E8EEF6",
                "border_color": self._mix_colors(menu_bg, button_fg, 0.55, fallback=button_fg),
            },
            "accent": {
                "fg_color": accent_bg,
                "hover_color": accent_hover_bg,
                "text_color": "#FFFFFF",
                "border_color": self._mix_colors(button_fg, accent_fg, 0.5, fallback=button_fg),
            },
            "system": {
                "fg_color": system_bg,
                "hover_color": system_hover,
                "text_color": "#E8EEF6",
                "border_color": self._mix_colors(menu_bg, button_fg, 0.7, fallback=button_fg),
            },
        }
        colors = palette.get(getattr(button, "_menu_style", "primary"), palette["primary"])
        try:
            # Keep style quick button resilient if this step fails.
            button.configure(
                fg_color=colors["fg_color"],
                hover_color=colors["hover_color"],
                text_color=colors["text_color"],
                font=self.BUTTON_FONT,
                border_width=1,
                border_color=colors["border_color"],
                height=self.QUICK_BUTTON_HEIGHT,
                corner_radius=self.QUICK_BUTTON_RADIUS,
            )
        except Exception:
            button.configure(
                fg_color=menu_bg,
                hover_color=button_fg,
                text_color=muted_fg,
            )
