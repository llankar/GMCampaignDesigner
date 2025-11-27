import tkinter as tk
import customtkinter as ctk

from modules.helpers import theme_manager
from modules.ui.tooltip import ToolTip
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


class IconDropdown(ctk.CTkFrame):
    """
    Compact dropdown that shows a grid of icon-only actions in a vertical list.

    Each option is represented by an icon and callback. The widget keeps the menu
    persistent (hidden when not in use) so callers can still access the underlying
    buttons for state updates.
    """

    def __init__(self, parent, items, default_key=None, button_size=(32, 32)):
        super().__init__(parent, fg_color="transparent")

        if not items:
            raise ValueError("IconDropdown requires at least one item")

        self._items = {item["key"]: item for item in items}
        self._order = [item["key"] for item in items]
        self._tokens = theme_manager.get_tokens()
        self._button_size = button_size
        self._default_key = default_key or self._order[0]
        self._selected_key = self._default_key

        self._menu = tk.Toplevel(self)
        self._menu.withdraw()
        self._menu.overrideredirect(True)
        self._menu.configure(bg=self._tokens.get("surface", "#1f1f1f"))
        self._menu.transient(self.winfo_toplevel())
        self._menu.bind("<FocusOut>", lambda _e: self._close_menu())

        self._option_buttons = {}
        self._build_menu()

        initial = self._items[self._selected_key]
        self._display_button = ctk.CTkButton(
            self,
            text="▼",
            image=initial["icon"],
            compound="right",
            width=self._button_size[0] + 18,
            height=self._button_size[1] + 10,
            corner_radius=12,
            fg_color=self._tokens.get("button_fg"),
            hover_color=self._tokens.get("button_hover"),
            border_width=1,
            border_color=self._tokens.get("button_border"),
            command=self._toggle_menu,
        )
        self._display_button.pack(side="left", padx=2, pady=2)
        ToolTip(self._display_button, initial.get("tooltip", ""))

        self.bind("<Destroy>", lambda _e: self._safe_destroy_menu())

    @property
    def option_buttons(self):
        return dict(self._option_buttons)

    def _build_menu(self):
        for key in self._order:
            item = self._items[key]
            btn = ctk.CTkButton(
                self._menu,
                text="",
                image=item["icon"],
                width=self._button_size[0] + 8,
                height=self._button_size[1] + 4,
                corner_radius=10,
                fg_color=self._tokens.get("button_fg"),
                hover_color=self._tokens.get("button_hover"),
                border_width=1,
                border_color=self._tokens.get("button_border"),
                command=lambda k=key: self._select(k),
            )
            btn.pack(fill="x", padx=6, pady=4)
            self._option_buttons[key] = btn
            if item.get("tooltip"):
                ToolTip(btn, item.get("tooltip"))

    def _toggle_menu(self):
        if self._menu.winfo_viewable():
            self._close_menu()
        else:
            self._open_menu()

    def _open_menu(self):
        if not self.winfo_ismapped():
            return
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self._menu.geometry(f"+{x}+{y}")
        self._menu.deiconify()
        self._menu.lift()
        self._menu.focus_force()

    def _close_menu(self):
        if self._menu:
            self._menu.withdraw()

    def _select(self, key):
        item = self._items.get(key)
        if not item:
            return
        self._selected_key = key
        self._display_button.configure(image=item["icon"])
        if callable(item.get("command")):
            item["command"]()
        self._close_menu()

    def set_active(self, key, active_style=None, default_style=None):
        active_style = active_style or {}
        default_style = default_style or {}

        for option_key, btn in self._option_buttons.items():
            style = active_style if option_key == key else default_style
            try:
                btn.configure(**style)
            except tk.TclError:
                continue

        target_key = key or self._default_key
        item = self._items.get(target_key)
        if item:
            try:
                self._display_button.configure(image=item["icon"])
            except tk.TclError:
                pass

    def _safe_destroy_menu(self):
        if self._menu:
            try:
                self._menu.destroy()
            except tk.TclError:
                pass
            self._menu = None
