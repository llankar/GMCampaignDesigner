import customtkinter as ctk
from tkinter import messagebox
from modules.factions.faction_editor_view import EditFactionWindow
import json
import os

class FactionsListView(ctk.CTkFrame):
    def __init__(self, master, data_file="factions.json", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.data_file = data_file
        self.factions = []
        self.filtered_factions = []
        self.search_var = ctk.StringVar()

        # Barre de recherche
        search_frame = ctk.CTkFrame(self)
        search_frame.pack(pady=5, fill="x")

        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_button = ctk.CTkButton(search_frame, text="Filter", command=self.filter_factions)
        search_button.pack(side="left", padx=5)

        # Bouton pour ajouter une faction
        add_button = ctk.CTkButton(self, text="Add Faction", command=self.add_item)
        add_button.pack(pady=5)

        # Cadre qui contiendra la liste des factions
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.pack(fill="both", expand=True)

        self.load_factions()
        self.refresh_list()

    def load_factions(self):
        """Charge les factions depuis le fichier JSON."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.factions = json.load(f)
            except json.JSONDecodeError:
                messagebox.showerror("Error", f"Could not decode JSON in {self.data_file}.")
                self.factions = []
        else:
            self.factions = []
        self.filtered_factions = self.factions.copy()

    def save_factions(self):
        """Sauvegarde les factions dans le fichier JSON."""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.factions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save to {self.data_file}.\n{e}")

    def refresh_list(self):
        """Met à jour l'affichage de la liste des factions."""
        # On efface d'abord tout le contenu du list_frame
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        # Pour chaque faction filtrée, on crée une ligne
        for faction in self.filtered_factions:
            row_frame = ctk.CTkFrame(self.list_frame)
            row_frame.pack(fill="x", padx=5, pady=5)

            # Nom de la faction
            faction_name = faction.get("Name", "Unknown")
            ctk.CTkLabel(row_frame, text=faction_name).pack(side="left", padx=5)

            # Description de la faction
            # -> Si c'est un dict (RichTextEditor), on récupère juste la clé "text"
            desc_data = faction.get("Description", "No Description")
            if isinstance(desc_data, dict):
                desc_str = desc_data.get("text", "")
            else:
                desc_str = desc_data
            ctk.CTkLabel(row_frame, text=desc_str).pack(side="left", padx=5)

            # Exemple si on veut afficher "Secrets" aussi dans la liste :
            # secrets_data = faction.get("Secrets", "")
            # if isinstance(secrets_data, dict):
            #     secrets_str = secrets_data.get("text", "")
            # else:
            #     secrets_str = secrets_data
            # ctk.CTkLabel(row_frame, text=secrets_str).pack(side="left", padx=5)

            edit_button = ctk.CTkButton(row_frame, text="Edit", command=lambda f=faction: self.edit_item(f))
            edit_button.pack(side="left", padx=5)

            delete_button = ctk.CTkButton(row_frame, text="Delete", command=lambda f=faction: self.delete_item(f))
            delete_button.pack(side="left", padx=5)

    def filter_factions(self):
        """Filtre la liste des factions en fonction de la chaîne de recherche."""
        search_text = self.search_var.get().lower()
        if not search_text:
            self.filtered_factions = self.factions.copy()
        else:
            self.filtered_factions = [
                f for f in self.factions
                if search_text in f.get("Name", "").lower()
                or (isinstance(f.get("Description", ""), dict)
                    and search_text in f["Description"].get("text", "").lower())
                or (isinstance(f.get("Description", ""), str)
                    and search_text in f["Description"].lower())
            ]
        self.refresh_list()

    def add_item(self):
        """Crée une nouvelle faction."""
        new_item = {}
        editor = EditFactionWindow(self, new_item, creation_mode=True)
        self.wait_window(editor)
        if editor.saved:
            self.factions.append(new_item)
            self.save_factions()
            self.filter_factions()

    def edit_item(self, faction):
        """Ouvre la fenêtre d'édition pour la faction."""
        editor = EditFactionWindow(self, faction, creation_mode=False)
        self.wait_window(editor)
        if editor.saved:
            self.save_factions()
            self.filter_factions()

    def delete_item(self, faction):
        """Supprime la faction sélectionnée."""
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{faction.get('Name', 'Unknown')}'?"):
            self.factions.remove(faction)
            self.save_factions()
            self.filter_factions()
