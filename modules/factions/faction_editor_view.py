import customtkinter as ctk
from modules.helpers.rich_text_editor import RichTextEditor

class EditFactionWindow(ctk.CTkToplevel):
    def __init__(self, master, faction, creation_mode=False):
        super().__init__(master)
        self.faction = faction
        self.saved = False

        self.title(f'{"Create" if creation_mode else "Edit"} Faction')
        self.geometry("1280x720")
        self.minsize(1280, 720)

        self.transient(master)
        self.lift()
        self.focus_force()

        # Récupération des données de description et secrets
        desc_data = faction.get("Description", "")
        secrets_data = faction.get("Secrets", "")

        # Pour la description : si les données sont formatées (dictionnaire), récupérer le texte, sinon utiliser le texte brut
        if isinstance(desc_data, dict):
            initial_desc = desc_data.get("text", "")
        else:
            initial_desc = desc_data

        # Pour les secrets
        if isinstance(secrets_data, dict):
            initial_secrets = secrets_data.get("text", "")
        else:
            initial_secrets = secrets_data

        # Champ "Name"
        ctk.CTkLabel(self, text="Name").pack(anchor="w", padx=10, pady=(10, 0))
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, faction.get("Name", ""))
        self.name_entry.pack(pady=5, fill="x", padx=10)

        # Champ "Description"
        ctk.CTkLabel(self, text="Description").pack(anchor="w", padx=10, pady=(10, 0))
        # On crée l'éditeur sans texte initial
        self.description_editor = RichTextEditor(self)
        self.description_editor.pack(pady=5, fill="both", expand=True, padx=10)
        # Charger le formatage si disponible, sinon insérer le texte brut
        if isinstance(desc_data, dict):
            self.description_editor.load_text_data(desc_data)
        else:
            self.description_editor.text_widget.insert("1.0", desc_data)

        # Champ "Secrets"
        ctk.CTkLabel(self, text="Secrets").pack(anchor="w", padx=10, pady=(10, 0))
        self.secrets_editor = RichTextEditor(self)
        self.secrets_editor.pack(pady=5, fill="both", expand=True, padx=10)
        if isinstance(secrets_data, dict):
            self.secrets_editor.load_text_data(secrets_data)
        else:
            self.secrets_editor.text_widget.insert("1.0", secrets_data)

        # Bouton de sauvegarde
        save_button = ctk.CTkButton(self, text="Save", command=self.save_faction)
        save_button.pack(pady=10)

    def save_faction(self):
        self.faction["Name"] = self.name_entry.get()
        # Sauvegarde du texte avec le formatage
        self.faction["Description"] = self.description_editor.get_text_data()
        self.faction["Secrets"] = self.secrets_editor.get_text_data()
        self.saved = True
        self.destroy()
