from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from modules.helpers import theme_manager
from modules.ui.menu.menu_sections import build_menu_specs, format_menu_label
from modules.ui.menu.quick_actions import build_primary_quick_actions, build_system_quick_actions


class AppMenuBar:
    """Custom in-window navigation bar with grouped menus and quick actions."""

    def __init__(self, app):
        self.app = app
        self._root_menu = tk.Menu(app)
        self._submenus: list[tk.Menu] = []
        self._menu_buttons: list[ctk.CTkButton] = []
        self._button_menus: list[tuple[ctk.CTkButton, tk.Menu]] = []
        self._open_menu: tk.Menu | None = None
        self._action_buttons: list[ctk.CTkButton] = []
        self._primary_quick_buttons: list[ctk.CTkButton] = []
        self._system_quick_buttons: list[ctk.CTkButton] = []

        self.frame = ctk.CTkFrame(app, corner_radius=0, height=42)
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
        self.quick_actions_inner.pack(anchor="center", pady=4)
        self.actions_frame.grid(row=0, column=2, sticky="e", padx=(4, 8))
        self.system_quick_frame.pack(side="left", padx=(0, 10), pady=4)
        self.utility_actions_frame.pack(side="right", pady=4)

        self._build()
        self.refresh_theme()

    def _apply_menu_theme(self, menu_widget: tk.Menu):
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
        for button in [*self._menu_buttons, *self._action_buttons, *self._primary_quick_buttons, *self._system_quick_buttons]:
            try:
                button.destroy()
            except Exception:
                pass
        self._submenus.clear()
        self._menu_buttons.clear()
        self._button_menus.clear()
        self._action_buttons.clear()
        self._primary_quick_buttons.clear()
        self._system_quick_buttons.clear()

    def _build(self):
        self._clear_widgets()
        for menu_spec in build_menu_specs(self.app):
            submenu = self._new_submenu()
            self._populate_submenu(submenu, menu_spec)
            self._add_menu_button(menu_spec.label, submenu)
        self._build_quick_actions()

    def rebuild(self):
        self._build()
        self.refresh_theme()

    def _new_submenu(self) -> tk.Menu:
        submenu = tk.Menu(self._root_menu, tearoff=0)
        self._apply_menu_theme(submenu)
        self._submenus.append(submenu)
        return submenu

    def _populate_submenu(self, submenu: tk.Menu, menu_spec):
        for group_index, group in enumerate(menu_spec.groups):
            submenu.add_command(label=group.title.upper(), state="disabled")
            submenu.add_command(label=f"  {group.helper}", state="disabled")
            for item in group.items:
                kwargs = {
                    "label": format_menu_label(item),
                    "command": item.command,
                }
                icon = self._get_icon(item.icon_key)
                if icon is not None:
                    kwargs["image"] = icon
                    kwargs["compound"] = "left"
                submenu.add_command(**kwargs)
            if group_index != len(menu_spec.groups) - 1:
                submenu.add_separator()

    def _popup_menu(self, menu: tk.Menu, button: ctk.CTkButton):
        if self._open_menu is not None:
            try:
                self._open_menu.unpost()
            except Exception:
                pass
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.post(x, y)
            self._open_menu = menu
        finally:
            menu.grab_release()

    def _on_root_click(self, event):
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
        button = ctk.CTkButton(
            self.menu_frame,
            text=label,
            width=96,
            height=32,
            corner_radius=10,
            border_width=0,
            command=None,
        )
        button.configure(command=lambda m=menu, b=button: self._popup_menu(m, b))
        button.pack(side="left", padx=(0, 6), pady=4)
        self._menu_buttons.append(button)
        self._button_menus.append((button, menu))

    def _build_quick_actions(self):
        for action in build_primary_quick_actions(self.app):
            button = self._create_quick_action_button(self.quick_actions_inner, action)
            button.pack(side="left", padx=4)
            self._primary_quick_buttons.append(button)
        for action in build_system_quick_actions(self.app):
            button = self._create_quick_action_button(self.system_quick_frame, action)
            button.pack(side="left", padx=4)
            self._system_quick_buttons.append(button)

    def _create_quick_action_button(self, parent, action_spec):
        icon = self._get_icon(action_spec.icon_key)
        button = ctk.CTkButton(
            parent,
            text=action_spec.text,
            image=icon,
            compound="left",
            height=28,
            width=max(88, len(action_spec.text) * 10 + 24),
            corner_radius=14,
            command=action_spec.command,
            font=("Segoe UI", 12, "bold"),
        )
        button._menu_style = action_spec.style
        return button

    def _get_icon(self, icon_key: str | None):
        return getattr(self.app, "icons", {}).get(icon_key) if icon_key else None

    def attach(self):
        self.app.configure(menu="")
        self.frame.pack(side="top", fill="x", before=getattr(self.app, "main_frame", None))
        self.app.bind_all("<Button-1>", self._on_root_click, add="+")

    def create_action_button(self, **kwargs) -> ctk.CTkButton:
        button = ctk.CTkButton(self.utility_actions_frame, height=24, corner_radius=12, **kwargs)
        button.pack(side="right", padx=(6, 0))
        self._action_buttons.append(button)
        return button

    def refresh_theme(self):
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
                button.configure(
                    fg_color=menu_bg,
                    hover_color=button_fg,
                    text_color="#E8EEF6",
                    font=("Segoe UI", 13, "bold"),
                    width=max(72, len(button.cget("text")) * 11),
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

        for button in self._action_buttons:
            try:
                if button.cget("fg_color") in ("", "transparent"):
                    button.configure(fg_color=menu_bg)
                if button.cget("hover_color") in ("", "transparent"):
                    button.configure(hover_color=button_fg)
                if button.cget("text_color") in ("", "transparent"):
                    button.configure(text_color="#E8EEF6")
            except Exception:
                pass

    def _style_quick_button(self, button, *, menu_bg: str, button_fg: str, panel_bg: str, muted_fg: str):
        palette = {
            "primary": {"fg_color": panel_bg, "hover_color": button_fg, "text_color": "#E8EEF6", "border_color": button_fg},
            "accent": {"fg_color": button_fg, "hover_color": "#2497FF", "text_color": "#FFFFFF", "border_color": button_fg},
            "system": {"fg_color": "#53361F", "hover_color": "#7A4D28", "text_color": "#FFE7C2", "border_color": "#B77A3A"},
        }
        colors = palette.get(getattr(button, "_menu_style", "primary"), palette["primary"])
        try:
            button.configure(
                fg_color=colors["fg_color"],
                hover_color=colors["hover_color"],
                text_color=colors["text_color"],
                border_width=1,
                border_color=colors["border_color"],
            )
        except Exception:
            button.configure(
                fg_color=menu_bg,
                hover_color=button_fg,
                text_color=muted_fg,
            )
