import customtkinter as ctk
from modules.helpers.rich_text_editor import RichTextEditor

class EditFactionWindow(ctk.CTkToplevel):
    def __init__(self, master, faction, creation_mode=False):
        super().__init__(master)
        self.faction = faction
        self.saved = False

        self.title(f'{"Create" if creation_mode else "Edit"} Faction')
        self.geometry("800x600")
        self.minsize(800, 600)

        self.transient(master)
        self.lift()
        self.focus_force()

        # === Cadre principal avec Scrollbar ===
        container = ctk.CTkScrollableFrame(self)
        container.pack(fill="both", expand=True)

        # === Name ===
        ctk.CTkLabel(container, text="Name").pack(anchor="w", padx=10, pady=(10, 0))
        self.name_entry = ctk.CTkEntry(container)
        self.name_entry.insert(0, faction.get("Name", ""))
        self.name_entry.pack(fill="x", padx=10, pady=5)

        # === Description ===
        ctk.CTkLabel(container, text="Description").pack(anchor="w", padx=10, pady=(10, 0))

        desc_data = faction.get("Description", "")
        if isinstance(desc_data, dict):
            initial_desc = desc_data.get("text", "")
        else:
            initial_desc = desc_data

        self.description_editor = RichTextEditor(container, initial_text=initial_desc)
        self.description_editor.pack(fill="both", expand=True, padx=10, pady=5)

        if isinstance(desc_data, dict):
            self.description_editor.load_text_data(desc_data)

        # === Secrets ===
        ctk.CTkLabel(container, text="Secrets").pack(anchor="w", padx=10, pady=(10, 0))

        secrets_data = faction.get("Secrets", "")
        if isinstance(secrets_data, dict):
            initial_secrets = secrets_data.get("text", "")
        else:
            initial_secrets = secrets_data

        self.secrets_editor = RichTextEditor(container, initial_text=initial_secrets)
        self.secrets_editor.pack(fill="both", expand=True, padx=10, pady=5)

        if isinstance(secrets_data, dict):
            self.secrets_editor.load_text_data(secrets_data)

        # === Bouton Save ===
        save_button = ctk.CTkButton(container, text="Save", command=self.save_faction)
        save_button.pack(pady=10)

    def save_faction(self):
        self.faction["Name"] = self.name_entry.get()
        self.faction["Description"] = self.description_editor.get_text_data()
        self.faction["Secrets"] = self.secrets_editor.get_text_data()
        self.saved = True
        self.destroy()
