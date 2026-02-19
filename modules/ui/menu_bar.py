import tkinter as tk
from tkinter import messagebox

from modules.helpers import theme_manager


class AppMenuBar:
    """Top application menu for MainWindow."""

    def __init__(self, app):
        self.app = app
        self.menu = tk.Menu(app)
        self._apply_menu_theme(self.menu)
        self._build()

    def _apply_menu_theme(self, menu_widget: tk.Menu):
        """Apply app-consistent colors and fonts to Tk menus."""
        tokens = theme_manager.get_tokens()
        menu_fg = "#E8EEF6"
        menu_bg = tokens.get("sidebar_header_bg", tokens.get("panel_alt_bg", "#132133"))
        active_bg = tokens.get("button_fg", "#0077CC")
        active_fg = "#FFFFFF"

        # Some Tk builds ignore per-widget menu colors for the top menubar.
        # Registering option defaults helps keep the menubar aligned with the
        # currently selected in-app theme.
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
        self._add_file_menu()
        self._add_campaign_menu()
        self._add_tools_menu()
        self._add_view_menu()
        self._add_help_menu()

    def _add_file_menu(self):
        file_menu = tk.Menu(self.menu, tearoff=0)
        self._apply_menu_theme(file_menu)
        file_menu.add_command(label="Change Database", command=self.app.change_database_storage, accelerator="F6")
        file_menu.add_separator()
        file_menu.add_command(label="Create Backup", command=self.app.prompt_campaign_backup)
        file_menu.add_command(label="Restore Backup", command=self.app.prompt_campaign_restore)
        file_menu.add_separator()
        file_menu.add_command(label="Export Scenarios", command=self.app.preview_and_export_scenarios)
        file_menu.add_command(label="Export Campaign Dossier", command=self.app.open_campaign_dossier_exporter)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.app.destroy, accelerator="F12")
        self.menu.add_cascade(label="File", menu=file_menu)

    def _add_campaign_menu(self):
        campaign_menu = tk.Menu(self.menu, tearoff=0)
        self._apply_menu_theme(campaign_menu)
        campaign_menu.add_command(label="Campaign Workshop", command=self.app.refresh_entities)
        campaign_menu.add_command(label="GM Screen", command=self.app.open_gm_screen, accelerator="F1")
        campaign_menu.add_command(label="World Map", command=self.app.open_world_map, accelerator="F5")
        campaign_menu.add_separator()
        campaign_menu.add_command(label="Character Graph", command=self.app.open_character_graph_editor)
        campaign_menu.add_command(label="Faction Graph", command=self.app.open_faction_graph_editor)
        campaign_menu.add_command(label="Scenario Graph", command=self.app.open_scenario_graph_editor)
        campaign_menu.add_command(label="Scene Flow Viewer", command=self.app.open_scene_flow_viewer)
        self.menu.add_cascade(label="Campaign", menu=campaign_menu)

    def _add_tools_menu(self):
        tools_menu = tk.Menu(self.menu, tearoff=0)
        self._apply_menu_theme(tools_menu)
        tools_menu.add_command(label="Generate Scenario", command=self.app.open_scenario_generator)
        tools_menu.add_command(label="Scenario Builder", command=self.app.open_scenario_builder, accelerator="F4")
        tools_menu.add_command(label="Import Scenario", command=self.app.open_scenario_importer)
        tools_menu.add_command(label="Import Creatures (PDF)", command=self.app.open_creature_importer)
        tools_menu.add_command(label="Import Objects (PDF)", command=self.app.open_object_importer)
        tools_menu.add_separator()
        tools_menu.add_command(label="Map Tool", command=self.app.map_tool, accelerator="F2")
        tools_menu.add_command(label="Whiteboard", command=self.app.open_whiteboard, accelerator="F3")
        tools_menu.add_command(label="Dice", command=self.app.open_dice_roller, accelerator="F8")
        tools_menu.add_command(label="Sound & Music", command=self.app.open_sound_manager, accelerator="F7")
        tools_menu.add_command(label="Session Timers", command=self.app.open_timer_window)
        self.menu.add_cascade(label="GM Tools", menu=tools_menu)

    def _add_view_menu(self):
        view_menu = tk.Menu(self.menu, tearoff=0)
        self._apply_menu_theme(view_menu)
        view_menu.add_command(label="Show Audio Bar", command=self.app.open_audio_bar)
        view_menu.add_command(label="Show Dice Bar", command=self.app.open_dice_bar)
        view_menu.add_command(label="Select System", command=self.app.open_system_selector)
        view_menu.add_command(label="Manage Systems", command=self.app.open_system_manager_dialog)
        view_menu.add_command(label="AI Settings", command=self.app.open_ai_settings)
        self.menu.add_cascade(label="View", menu=view_menu)

    def _add_help_menu(self):
        help_menu = tk.Menu(self.menu, tearoff=0)
        self._apply_menu_theme(help_menu)
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
        self.menu.add_cascade(label="Help", menu=help_menu)

    def attach(self):
        self.app.configure(menu=self.menu)
