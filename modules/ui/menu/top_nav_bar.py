from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from modules.ui.menu.menu_image_adapter import prepare_menu_image, resize_ctk_icon
from modules.ui.menu.menu_sections import build_menu_specs, format_menu_label
from modules.ui.menu.menu_visual_state import MenuLayoutController, MenuVisualPalette
from modules.ui.menu.menu_widgets import (
    MenuBarLayoutApplier,
    MenuChrome,
    MenuChromeOptions,
    QuickActionButton,
    TopLevelMenuButton,
)
from modules.ui.menu.quick_actions import build_primary_quick_actions, build_system_quick_actions


class AppMenuBar:
    """Custom in-window navigation bar with grouped menus and quick actions."""

    FRAME_HEIGHT = 18
    LAYOUT_WIDTH_DELTA_THRESHOLD = 32
    MENU_BUTTON_HEIGHT = 14
    MENU_BUTTON_WIDTH = 70
    MENU_FONT = ("Segoe UI", 10, "bold")
    MENU_ICON_SIZE = (30, 30)
    QUICK_ICON_SIZE = (16, 16)
    QUICK_BUTTON_HEIGHT = 16
    QUICK_BUTTON_RADIUS = 8
    QUICK_BUTTON_MIN_WIDTH = 64
    QUICK_BUTTON_WIDTH_SCALE = 7

    def __init__(self, app):
        self.app = app
        self._root_menu = tk.Menu(app)
        self._submenus: list[tk.Menu] = []
        self._menu_buttons: list[ctk.CTkButton] = []
        self._button_menus: list[tuple[ctk.CTkButton, tk.Menu]] = []
        self._menu_controllers: list[TopLevelMenuButton] = []
        self._menu_controller_map: dict[ctk.CTkButton, TopLevelMenuButton] = {}
        self._open_menu: tk.Menu | None = None
        self._open_menu_button: ctk.CTkButton | None = None
        self._menu_images: list[tk.PhotoImage] = []
        self._action_buttons: list[ctk.CTkButton] = []
        self._primary_quick_buttons: list[ctk.CTkButton] = []
        self._system_quick_buttons: list[ctk.CTkButton] = []
        self._primary_quick_controllers: list[QuickActionButton] = []
        self._system_quick_controllers: list[QuickActionButton] = []
        self._layout_mode = "expanded"
        self._last_palette = MenuVisualPalette.from_theme()
        self._last_layout_width: int | None = None
        self._last_layout_metrics = None
        self._last_configure_width: int | None = None
        self._pending_layout_width: int | None = None
        self._layout_after_id: str | None = None

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
        self.chrome = MenuChrome(app, options=MenuChromeOptions(show_divider=True, show_shadow=True))

        self.menu_frame.grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.quick_actions_frame.grid(row=0, column=1, sticky="ew")
        self.quick_actions_inner.pack(anchor="center", pady=1)
        self.actions_frame.grid(row=0, column=2, sticky="e", padx=(4, 8))
        self.system_quick_frame.pack(side="left", padx=(0, 8), pady=1)
        self.utility_actions_frame.pack(side="right", pady=1)

        self._build()
        self.refresh_theme()

    def _apply_menu_theme(self, menu_widget: tk.Menu):
        palette = self._last_palette or MenuVisualPalette.from_theme()
        self.app.option_add("*Menu.background", palette.menu_bg)
        self.app.option_add("*Menu.foreground", palette.text_color)
        self.app.option_add("*Menu.activeBackground", palette.active_bg)
        self.app.option_add("*Menu.activeForeground", palette.active_text)
        self.app.option_add("*Menu.disabledForeground", palette.muted_text_color)

        menu_widget.configure(
            bg=palette.menu_bg,
            fg=palette.text_color,
            activebackground=palette.active_bg,
            activeforeground=palette.active_text,
            disabledforeground=palette.muted_text_color,
            selectcolor=palette.active_bg,
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
        self._menu_controller_map.clear()
        self._menu_controllers.clear()
        self._menu_images.clear()
        self._action_buttons.clear()
        self._primary_quick_buttons.clear()
        self._system_quick_buttons.clear()
        self._primary_quick_controllers.clear()
        self._system_quick_controllers.clear()
        self._open_menu = None
        self._open_menu_button = None

    def _build(self):
        self._clear_widgets()
        for menu_spec in build_menu_specs(self.app):
            submenu = self._new_submenu()
            self._populate_submenu(submenu, menu_spec)
            self._add_menu_button(menu_spec.label, submenu)
        self._build_quick_actions()
        self._apply_layout(self._current_width())

    def rebuild(self):
        self._build()
        self.refresh_theme()

    def _new_submenu(self) -> tk.Menu:
        submenu = tk.Menu(self._root_menu, tearoff=0)
        self._apply_menu_theme(submenu)
        try:
            submenu.bind("<Unmap>", lambda _event, m=submenu: self._handle_menu_unpost(m), add="+")
        except Exception:
            pass
        self._submenus.append(submenu)
        return submenu

    def _populate_submenu(self, submenu: tk.Menu, menu_spec):
        for group_index, group in enumerate(menu_spec.groups):
            submenu.add_command(label=group.title.upper(), state="disabled")
            submenu.add_command(label=f"  {group.helper}", state="disabled")
            for item in group.items:
                kwargs = {
                    "label": format_menu_label(item),
                    "command": self._wrap_menu_command(item.command),
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

    def _wrap_menu_command(self, command):
        if command is None:
            return None

        def _runner():
            self._close_open_menu()
            command()

        return _runner

    def _popup_menu(self, menu: tk.Menu, button: ctk.CTkButton):
        is_same_menu = self._open_menu is menu and self._open_menu_button is button
        if is_same_menu:
            self._close_open_menu()
            return
        self._close_open_menu()
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.post(x, y)
            self._open_menu = menu
            self._set_open_menu_button(button)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _on_root_click(self, event):
        if self._open_menu is None:
            return
        widget = event.widget
        for button, _menu in self._button_menus:
            if widget is button:
                return
        if widget is self._open_menu:
            return
        self._close_open_menu()

    def _set_open_menu_button(self, button: ctk.CTkButton | None):
        if self._open_menu_button is button:
            return
        previous = self._open_menu_button
        self._open_menu_button = button
        if previous is not None:
            self._set_top_level_button_state(previous, is_open=False)
        if button is not None:
            self._set_top_level_button_state(button, is_open=True)

    def _set_top_level_button_state(self, button: ctk.CTkButton, *, is_open: bool | None = None, is_active: bool | None = None):
        controller = self._menu_controller_map.get(button)
        if controller is None:
            return
        if is_open is not None:
            controller.is_open = is_open
            if is_open:
                controller.is_active = True
            elif is_active is None:
                controller.is_active = False
        if is_active is not None:
            controller.is_active = is_active
        controller.apply_theme(self._last_palette, width=self._menu_button_width(controller.button))

    def _handle_menu_unpost(self, menu: tk.Menu):
        if self._open_menu is menu:
            self._close_open_menu(menu=menu)

    def _close_open_menu(self, *, menu: tk.Menu | None = None):
        target = menu or self._open_menu
        self._open_menu = None
        self._set_open_menu_button(None)
        if target is not None:
            try:
                target.unpost()
            except Exception:
                pass

    def _add_menu_button(self, label: str, menu: tk.Menu):
        controller = TopLevelMenuButton(
            self.menu_frame,
            label=label,
            command=lambda m=menu, b=None: None,
            width=self.MENU_BUTTON_WIDTH,
            height=self.MENU_BUTTON_HEIGHT,
            font=self.MENU_FONT,
        )
        button = controller.button
        button.configure(command=lambda m=menu, b=button: self._popup_menu(m, b), font=self.MENU_FONT)
        controller.pack(side="left", padx=(0, 4), pady=1)
        self._menu_buttons.append(button)
        self._button_menus.append((button, menu))
        self._menu_controllers.append(controller)
        self._menu_controller_map[button] = controller

    def _build_quick_actions(self):
        for action in build_primary_quick_actions(self.app):
            controller = self._create_quick_action_button(self.quick_actions_inner, action)
            controller.pack(side="left", padx=4)
            self._primary_quick_controllers.append(controller)
            self._primary_quick_buttons.append(controller.button)
        for action in build_system_quick_actions(self.app):
            controller = self._create_quick_action_button(self.system_quick_frame, action)
            controller.pack(side="left", padx=4)
            self._system_quick_controllers.append(controller)
            self._system_quick_buttons.append(controller.button)

    def _create_quick_action_button(self, parent, action_spec) -> QuickActionButton:
        icon = resize_ctk_icon(self._get_icon(action_spec.icon_key), self.QUICK_ICON_SIZE)
        controller = QuickActionButton(
            parent,
            text=action_spec.text,
            image=icon,
            command=action_spec.command,
            style=action_spec.style,
            width=max(self.QUICK_BUTTON_MIN_WIDTH, len(action_spec.text) * self.QUICK_BUTTON_WIDTH_SCALE + 18),
            height=self.QUICK_BUTTON_HEIGHT,
            corner_radius=self.QUICK_BUTTON_RADIUS,
            font=("Segoe UI", 10, "bold"),
            border_spacing=4,
        )
        controller.button._menu_style = action_spec.style
        return controller

    def _get_icon(self, icon_key: str | None):
        return getattr(self.app, "icons", {}).get(icon_key) if icon_key else None

    def attach(self):
        self.app.configure(menu="")
        self.frame.pack(side="top", fill="x", before=getattr(self.app, "main_frame", None))
        self.chrome.pack(side="top", fill="x", before=getattr(self.app, "main_frame", None))
        self.app.bind_all("<Button-1>", self._on_root_click, add="+")
        try:
            self.app.bind("<Configure>", self._on_app_configure, add="+")
        except Exception:
            pass
        self._queue_layout(self._current_width(), force=True)

    def create_action_button(self, **kwargs) -> ctk.CTkButton:
        button = ctk.CTkButton(self.utility_actions_frame, height=16, corner_radius=8, **kwargs)
        button.pack(side="right", padx=(6, 0))
        self._action_buttons.append(button)
        return button

    def refresh_theme(self):
        self._last_palette = MenuVisualPalette.from_theme()
        palette = self._last_palette

        self.frame.configure(fg_color=palette.menu_bg)
        self.menu_frame.configure(fg_color="transparent")
        self.quick_actions_frame.configure(fg_color="transparent")
        self.quick_actions_inner.configure(fg_color="transparent")
        self.actions_frame.configure(fg_color="transparent")
        self.system_quick_frame.configure(fg_color="transparent")
        self.utility_actions_frame.configure(fg_color="transparent")
        self.chrome.apply_theme(palette)

        for controller in self._menu_controllers:
            try:
                controller.button.configure(font=self.MENU_FONT)
                controller.apply_theme(palette, width=self._menu_button_width(controller.button))
            except Exception:
                pass

        for submenu in self._submenus:
            try:
                self._apply_menu_theme(submenu)
            except Exception:
                pass

        for controller in self._primary_quick_controllers:
            controller.apply_theme(palette)
        for controller in self._system_quick_controllers:
            controller.apply_theme(palette)

        for button in self._action_buttons:
            try:
                if button.cget("fg_color") in ("", "transparent"):
                    button.configure(fg_color=palette.menu_bg)
                if button.cget("hover_color") in ("", "transparent"):
                    button.configure(hover_color=palette.button_fg)
                if button.cget("text_color") in ("", "transparent"):
                    button.configure(text_color=palette.text_color)
                if button.cget("border_color") in ("", "transparent"):
                    button.configure(border_color=palette.button_border)
            except Exception:
                pass

        self._apply_layout(self._current_width())

    def _menu_button_width(self, button: ctk.CTkButton) -> int:
        text = button.cget("text")
        base = 64 if self._layout_mode == "compact" else 72
        scale = 8 if self._layout_mode == "compact" else 9
        return max(base, len(text) * scale)

    def _apply_layout(self, width: int):
        metrics = MenuLayoutController.resolve(width)
        metrics_changed = metrics != self._last_layout_metrics
        width_changed = width != self._last_layout_width
        self._layout_mode = metrics.mode
        self._last_layout_width = width

        if metrics_changed:
            MenuBarLayoutApplier.apply(
                self._menu_controllers,
                self._primary_quick_controllers,
                self._system_quick_controllers,
                menu_frame=self.menu_frame,
                quick_actions_inner=self.quick_actions_inner,
                actions_frame=self.actions_frame,
                system_quick_frame=self.system_quick_frame,
                utility_actions_frame=self.utility_actions_frame,
                metrics=metrics,
            )
            self._last_layout_metrics = metrics

        if metrics_changed or width_changed:
            for controller in self._menu_controllers:
                controller.apply_theme(self._last_palette, width=self._menu_button_width(controller.button))

    def _current_width(self) -> int:
        try:
            width = int(self.app.winfo_width())
            if width > 1:
                return width
        except Exception:
            pass
        return 1600

    def _parse_layout_width(self, width) -> int | None:
        try:
            parsed_width = int(width)
        except (TypeError, ValueError):
            return None
        if parsed_width <= 1:
            return None
        return parsed_width

    def _has_meaningful_layout_change(self, width: int, metrics=None) -> bool:
        metrics = metrics or MenuLayoutController.resolve(width)
        last_mode = self._last_layout_metrics.mode if self._last_layout_metrics is not None else self._layout_mode
        if metrics.mode != last_mode:
            return True

        comparison_widths = (
            self._pending_layout_width,
            self._last_layout_width,
            self._last_configure_width,
        )
        for previous_width in comparison_widths:
            if previous_width is None:
                continue
            if abs(width - previous_width) >= self.LAYOUT_WIDTH_DELTA_THRESHOLD:
                return True
        return all(previous_width is None for previous_width in comparison_widths)

    def _queue_layout(self, width: int, *, force: bool = False):
        parsed_width = self._parse_layout_width(width)
        if parsed_width is None:
            return

        metrics = MenuLayoutController.resolve(parsed_width)
        if not force:
            if (
                parsed_width == self._last_layout_width
                or parsed_width == self._last_configure_width
                or parsed_width == self._pending_layout_width
            ):
                return
            if not self._has_meaningful_layout_change(parsed_width, metrics):
                self._last_configure_width = parsed_width
                return

        self._pending_layout_width = parsed_width
        if self._layout_after_id is not None:
            try:
                self.app.after_cancel(self._layout_after_id)
            except Exception:
                pass
        self._layout_after_id = self.app.after_idle(self._flush_layout)

    def _flush_layout(self):
        self._layout_after_id = None
        width = self._pending_layout_width
        self._pending_layout_width = None
        if width is None:
            return
        self._last_configure_width = width
        self._apply_layout(width)

    def _on_app_configure(self, event):
        width = self._parse_layout_width(getattr(event, "width", None))
        if width is None:
            return
        self._queue_layout(width)
