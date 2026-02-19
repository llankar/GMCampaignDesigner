import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.helpers import theme_manager


class AppMenuBar:
    """Custom in-window menu bar with themed buttons and Tk popup menus."""

    def __init__(self, app):
        self.app = app
        self._root_menu = tk.Menu(app)
        self._submenus: list[tk.Menu] = []
        self._menu_buttons: list[ctk.CTkButton] = []
        self._button_menus: list[tuple[ctk.CTkButton, tk.Menu]] = []
        self._open_menu: tk.Menu | None = None
        self.frame = ctk.CTkFrame(app, corner_radius=0, height=34)
        self._build()
        self.refresh_theme()

    def _apply_menu_theme(self, menu_widget: tk.Menu):
        """Apply app-consistent colors and fonts to popup menus."""
        tokens = theme_manager.get_tokens()
        menu_fg = "#E8EEF6"
        menu_bg = tokens.get("sidebar_header_bg", tokens.get("panel_alt_bg", "#132133"))
        active_bg = tokens.get("button_fg", "#0077CC")
        active_fg = "#FFFFFF"

        self.app.option_add("*Menu.background", menu_bg)
        self.app.option_add("*Menu.foreground", menu_fg)
        self.app.option_add("*Menu.activeBackground", active_bg)
        self.app.option_add("*Menu.activeForeground", active_fg)

        menu_widget.configure(
            bg=menu_bg,
            fg=menu_fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            selectcolor=active_bg,
            font=("Segoe UI", 10),
            borderwidth=0,
            tearoff=0,
        )

    def _build(self):
        self._submenus.clear()
        self._menu_buttons.clear()
        self._button_menus.clear()

        self._add_file_menu()
        self._add_campaign_menu()
        self._add_tools_menu()
        self._add_view_menu()
        self._add_help_menu()

    def _new_submenu(self) -> tk.Menu:
        submenu = tk.Menu(self._root_menu, tearoff=0)
        self._apply_menu_theme(submenu)
        self._submenus.append(submenu)
        return submenu

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
            self.frame,
            text=label,
            width=96,
            corner_radius=0,
            border_width=0,
            command=None,
        )
        button.configure(command=lambda m=menu, b=button: self._popup_menu(m, b))
        button.pack(side="left", padx=(0, 1), pady=0)
        self._menu_buttons.append(button)
        self._button_menus.append((button, menu))

    def _add_file_menu(self):
        file_menu = self._new_submenu()
        file_menu.add_command(label="Change Database\t F6", command=self.app.change_database_storage)
        file_menu.add_separator()
        file_menu.add_command(label="Create Backup", command=self.app.prompt_campaign_backup)
        file_menu.add_command(label="Restore Backup", command=self.app.prompt_campaign_restore)
        file_menu.add_separator()
        file_menu.add_command(label="Export Scenarios", command=self.app.preview_and_export_scenarios)
        file_menu.add_command(label="Export Campaign Dossier", command=self.app.open_campaign_dossier_exporter)
        file_menu.add_separator()
        file_menu.add_command(label="Quit\t F12", command=self.app.destroy)
        self._add_menu_button("File", file_menu)

    def _add_campaign_menu(self):
        campaign_menu = self._new_submenu()
        campaign_menu.add_command(label="Campaign Workshop", command=self.app.refresh_entities)
        campaign_menu.add_command(label="GM Screen\t F1", command=self.app.open_gm_screen)
        campaign_menu.add_command(label="World Map\t F5", command=self.app.open_world_map)
        campaign_menu.add_separator()
        campaign_menu.add_command(label="Character Graph", command=self.app.open_character_graph_editor)
        campaign_menu.add_command(label="Faction Graph", command=self.app.open_faction_graph_editor)
        campaign_menu.add_command(label="Scenario Graph", command=self.app.open_scenario_graph_editor)
        campaign_menu.add_command(label="Scene Flow Viewer", command=self.app.open_scene_flow_viewer)
        self._add_menu_button("Campaign", campaign_menu)

    def _add_tools_menu(self):
        tools_menu = self._new_submenu()
        tools_menu.add_command(label="Generate Scenario", command=self.app.open_scenario_generator)
        tools_menu.add_command(label="Scenario Builder\t F4", command=self.app.open_scenario_builder)
        tools_menu.add_command(label="Import Scenario", command=self.app.open_scenario_importer)
        tools_menu.add_command(label="Import Creatures (PDF)", command=self.app.open_creature_importer)
        tools_menu.add_command(label="Import Objects (PDF)", command=self.app.open_object_importer)
        tools_menu.add_separator()
        tools_menu.add_command(label="Map Tool\t F2", command=self.app.map_tool)
        tools_menu.add_command(label="Whiteboard\t F3", command=self.app.open_whiteboard)
        tools_menu.add_command(label="Dice\t F8", command=self.app.open_dice_roller)
        tools_menu.add_command(label="Sound & Music\t F7", command=self.app.open_sound_manager)
        tools_menu.add_command(label="Session Timers", command=self.app.open_timer_window)
        self._add_menu_button("GM Tools", tools_menu)

    def _add_view_menu(self):
        view_menu = self._new_submenu()
        view_menu.add_command(label="Show Audio Bar", command=self.app.open_audio_bar)
        view_menu.add_command(label="Show Dice Bar", command=self.app.open_dice_bar)
        view_menu.add_command(label="Select System", command=self.app.open_system_selector)
        view_menu.add_command(label="Manage Systems", command=self.app.open_system_manager_dialog)
        view_menu.add_command(label="AI Settings", command=self.app.open_ai_settings)
        self._add_menu_button("View", view_menu)

    def _add_help_menu(self):
        help_menu = self._new_submenu()
        help_menu.add_command(
            label="Shortcuts",
            command=lambda: messagebox.showinfo(
                "Keyboard Shortcuts",
                "F1: GM Screen\n"
                "F2: Map Tool\n"
                "F3: Whiteboard\n"
                "F4: Scenario Builder\n"
                "F5: World Map\n"
                "F6: Change Database\n"
                "F7: Sound & Music\n"
                "F8: Dice\n"
                "F12: Quit",
            ),
        )
        self._add_menu_button("Help", help_menu)

    def attach(self):
        self.app.configure(menu="")
        self.frame.pack(side="top", fill="x", before=getattr(self.app, "main_frame", None))
        self.app.bind_all("<Button-1>", self._on_root_click, add="+")

    def refresh_theme(self):
        """Re-apply colors after a theme change."""
        tokens = theme_manager.get_tokens()
        menu_bg = tokens.get("sidebar_header_bg", tokens.get("panel_alt_bg", "#132133"))
        button_fg = tokens.get("button_fg", "#0077CC")

        self.frame.configure(fg_color=menu_bg)

        for button in self._menu_buttons:
            try:
                button.configure(
                    fg_color=menu_bg,
                    hover_color=button_fg,
                    text_color="#E8EEF6",
                    font=("Segoe UI", 13),
                    width=max(72, len(button.cget("text")) * 11),
                )
            except Exception:
                pass

        for submenu in self._submenus:
            try:
                self._apply_menu_theme(submenu)
            except Exception:
                pass
