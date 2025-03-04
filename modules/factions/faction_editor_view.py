import customtkinter as ctk
from modules.helpers.rich_text_editor import RichTextEditor

class EditFactionWindow(ctk.CTkToplevel):
    def __init__(self, master, faction, creation_mode=False):
        super().__init__(master)
        self.faction = faction
        self.saved = False

        self.title(f'{"Create" if creation_mode else "Edit"} Faction')
        
        
        self.transient(master)
        self.lift()
        self.focus_force()
        
        # Create a scrollable frame to hold all content
        scrollable_frame = ctk.CTkScrollableFrame(self, width=1240, height=680)
        scrollable_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        # For this example, we assume the faction dictionary may store formatted text as a dict.
        # If not, fall back to plain text.
        desc_data = faction.get("Description", "")
        if isinstance(desc_data, dict):
            initial_desc = desc_data.get("text", "")
        else:
            initial_desc = desc_data

        secrets_data = faction.get("Secrets", "")
        if isinstance(secrets_data, dict):
            initial_secrets = secrets_data.get("text", "")
        else:
            initial_secrets = secrets_data

        # Add the widgets into the scrollable frame
        ctk.CTkLabel(scrollable_frame, text="Name").pack(anchor="w", padx=10, pady=(10, 0))
        self.name_entry = ctk.CTkEntry(scrollable_frame)
        self.name_entry.insert(0, faction.get("Name", ""))
        self.name_entry.pack(pady=5, fill="x", padx=10)

        ctk.CTkLabel(scrollable_frame, text="Description").pack(anchor="w", padx=10, pady=(10, 0))
        self.description_editor = RichTextEditor(scrollable_frame, initial_text=initial_desc)
        # If formatted data exists, load it to reapply formatting.
        if isinstance(desc_data, dict):
            self.description_editor.load_text_data(desc_data)
        self.description_editor.pack(pady=5, fill="both", expand=True, padx=10)

        ctk.CTkLabel(scrollable_frame, text="Secrets").pack(anchor="w", padx=10, pady=(10, 0))
        self.secrets_editor = RichTextEditor(scrollable_frame, initial_text=initial_secrets)
        if isinstance(secrets_data, dict):
            self.secrets_editor.load_text_data(secrets_data)
        self.secrets_editor.pack(pady=5, fill="both", expand=True, padx=10)

        save_button = ctk.CTkButton(scrollable_frame, text="Save", command=self.save_faction)
        save_button.pack(pady=10)

    def save_faction(self):
        self.faction["Name"] = self.name_entry.get()
        # Save the text along with formatting metadata:
        self.faction["Description"] = self.description_editor.get_text_data()
        self.faction["Secrets"] = self.secrets_editor.get_text_data()
        self.saved = True
        self.destroy()
