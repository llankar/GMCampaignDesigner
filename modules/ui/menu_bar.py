import tkinter as tk
from tkinter import messagebox


class AppMenuBar:
    """Top application menu for MainWindow."""

    def __init__(self, app):
        self.app = app
        self.menu = tk.Menu(app)
        self._build()

    def _build(self):
        self._add_file_menu()
        self._add_campaign_menu()
        self._add_tools_menu()
        self._add_view_menu()
        self._add_help_menu()

    def _add_file_menu(self):
        file_menu = tk.Menu(self.menu, tearoff=0)
        file_menu.add_command(label="Changer de base de données", command=self.app.change_database_storage, accelerator="F6")
        file_menu.add_separator()
        file_menu.add_command(label="Créer une sauvegarde", command=self.app.prompt_campaign_backup)
        file_menu.add_command(label="Restaurer une sauvegarde", command=self.app.prompt_campaign_restore)
        file_menu.add_separator()
        file_menu.add_command(label="Exporter les scénarios", command=self.app.preview_and_export_scenarios)
        file_menu.add_command(label="Exporter dossier de campagne", command=self.app.open_campaign_dossier_exporter)
        file_menu.add_command(label="Exporter vers Foundry", command=self.app.export_foundry)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.app.destroy, accelerator="F12")
        self.menu.add_cascade(label="Fichier", menu=file_menu)

    def _add_campaign_menu(self):
        campaign_menu = tk.Menu(self.menu, tearoff=0)
        campaign_menu.add_command(label="Atelier de campagne", command=self.app.refresh_entities)
        campaign_menu.add_command(label="Écran MJ", command=self.app.open_gm_screen, accelerator="F1")
        campaign_menu.add_command(label="World Map", command=self.app.open_world_map, accelerator="F5")
        campaign_menu.add_separator()
        campaign_menu.add_command(label="Graphe personnages", command=self.app.open_character_graph_editor)
        campaign_menu.add_command(label="Graphe factions", command=self.app.open_faction_graph_editor)
        campaign_menu.add_command(label="Graphe scénarios", command=self.app.open_scenario_graph_editor)
        campaign_menu.add_command(label="Scene Flow Viewer", command=self.app.open_scene_flow_viewer)
        self.menu.add_cascade(label="Campagne", menu=campaign_menu)

    def _add_tools_menu(self):
        tools_menu = tk.Menu(self.menu, tearoff=0)
        tools_menu.add_command(label="Générer un scénario", command=self.app.open_scenario_generator)
        tools_menu.add_command(label="Assistant de scénario", command=self.app.open_scenario_builder, accelerator="F4")
        tools_menu.add_command(label="Importer un scénario", command=self.app.open_scenario_importer)
        tools_menu.add_command(label="Importer créatures (PDF)", command=self.app.open_creature_importer)
        tools_menu.add_command(label="Importer objets (PDF)", command=self.app.open_object_importer)
        tools_menu.add_separator()
        tools_menu.add_command(label="Outil de carte", command=self.app.map_tool, accelerator="F2")
        tools_menu.add_command(label="Whiteboard", command=self.app.open_whiteboard, accelerator="F3")
        tools_menu.add_command(label="Dés", command=self.app.open_dice_roller, accelerator="F8")
        tools_menu.add_command(label="Son & musique", command=self.app.open_sound_manager, accelerator="F7")
        tools_menu.add_command(label="Timers de session", command=self.app.open_timer_window)
        self.menu.add_cascade(label="Outils MJ", menu=tools_menu)

    def _add_view_menu(self):
        view_menu = tk.Menu(self.menu, tearoff=0)
        view_menu.add_command(label="Afficher la barre audio", command=self.app.open_audio_bar)
        view_menu.add_command(label="Afficher la barre de dés", command=self.app.open_dice_bar)
        view_menu.add_command(label="Sélectionner le système", command=self.app.open_system_selector)
        view_menu.add_command(label="Gérer les systèmes", command=self.app.open_system_manager_dialog)
        view_menu.add_command(label="Paramètres IA", command=self.app.open_ai_settings)
        self.menu.add_cascade(label="Affichage", menu=view_menu)

    def _add_help_menu(self):
        help_menu = tk.Menu(self.menu, tearoff=0)
        help_menu.add_command(
            label="Raccourcis",
            command=lambda: messagebox.showinfo(
                "Raccourcis clavier",
                "F1: Écran MJ\n"
                "F2: Outil de carte\n"
                "F3: Whiteboard\n"
                "F4: Assistant scénario\n"
                "F5: World Map\n"
                "F6: Changer base de données\n"
                "F7: Son & musique\n"
                "F8: Dés\n"
                "F12: Quitter",
            ),
        )
        self.menu.add_cascade(label="Aide", menu=help_menu)

    def attach(self):
        self.app.configure(menu=self.menu)

