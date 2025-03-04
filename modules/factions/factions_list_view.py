import customtkinter as ctk
from tkinter import messagebox
from modules.factions.faction_editor_view import EditFactionWindow
import json
import os

from modules.factions.factions_model import load_factions, save_factions, load_template
from modules.factions.helpers import format_longtext


class FactionsListView(ctk.CTkFrame):
    def __init__(self, master, data_file="factions.json", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.data_file = data_file

        # Chargement des factions et du template
        self.factions = load_factions()
        self.filtered_factions = self.factions.copy()
        self.template = load_template()

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

        # Table/liste affichant les factions
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.pack(fill="both", expand=True)

        # Chargement initial
        self.refresh_list()

    def refresh_list(self):
        """Affiche la liste filtrée des factions."""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not self.filtered_factions:
            ctk.CTkLabel(self.list_frame, text="No factions found.").pack(pady=10)
            return

        # Création des entêtes (header)
        header_frame = ctk.CTkFrame(self.list_frame)
        header_frame.pack(fill="x", pady=5)

        for field in self.template["fields"]:
            ctk.CTkLabel(header_frame, text=field["name"], anchor="w").pack(side="left", padx=5, expand=True)

        ctk.CTkLabel(header_frame, text="Actions", anchor="w").pack(side="left", padx=5)

        # Création des lignes
        for faction in self.filtered_factions:
            self.create_item_row(faction)

    def create_item_row(self, faction):
        row_frame = ctk.CTkFrame(self.list_frame)
        row_frame.pack(fill="x", pady=2)
        for field in self.template["fields"]:
            value = faction.get(field["name"], "")
            if field["type"] == "longtext":
                if isinstance(value, dict):
                    value = value.get("text", "")  # On ne garde que le texte
                value = format_longtext(value, max_length=50)

            ctk.CTkLabel(row_frame, text=value, anchor="w").pack(side="left", padx=5, expand=True)

        action_frame = ctk.CTkFrame(row_frame)
        action_frame.pack(side="left", padx=5)

        edit_button = ctk.CTkButton(action_frame, text="Edit", width=60, command=lambda: self.edit_item(faction))
        edit_button.pack(side="left", padx=2)

        delete_button = ctk.CTkButton(action_frame, text="Delete", width=60, command=lambda: self.delete_item(faction))
        delete_button.pack(side="left", padx=2)


    def filter_factions(self):
        """Filtrage basé sur la recherche."""
        query = self.search_var.get().strip().lower()

        if not query:
            self.filtered_factions = self.factions.copy()
        else:
            self.filtered_factions = [
                faction for faction in self.factions
                if query in faction.get("Name", "").lower()
                or self.match_longtext(faction.get("Description", ""), query)
                or self.match_longtext(faction.get("Secrets", ""), query)
            ]

        self.refresh_list()

    def match_longtext(self, data, query):
        """Recherche textuelle dans les champs longtext."""
        if isinstance(data, dict):
            text = data.get("text", "").lower()
        else:
            text = str(data).lower()
        return query in text

    def add_item(self):
        """Créer une nouvelle faction."""
        new_faction = {}
        editor = EditFactionWindow(self, new_faction, creation_mode=True)
        self.wait_window(editor)

        if editor.saved:
            self.factions.append(new_faction)
            save_factions(self.factions)
            self.filter_factions()

    def edit_item(self, faction):
        """Modifier une faction existante."""
        editor = EditFactionWindow(self, faction, creation_mode=False)
        self.wait_window(editor)

        if editor.saved:
            save_factions(self.factions)
            self.filter_factions()

    def delete_item(self, faction):
        """Supprimer une faction."""
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{faction.get('Name', 'Unknown')}'?"):
            self.factions.remove(faction)
            save_factions(self.factions)
            self.filter_factions()
