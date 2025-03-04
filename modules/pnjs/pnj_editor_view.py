
import customtkinter as ctk
import tkinter as tk
from modules.pnjs.pnjs_model import load_template
from modules.factions.factions_model import load_factions

def get_faction_names():
    return [faction["Name"] for faction in load_factions()]

class EditNPCWindow(ctk.CTkToplevel):
    def __init__(self, master, npc, creation_mode=False):
        super().__init__(master)
        self.npc = npc
        self.saved = False
        self.template = load_template()

        self.title(f'{"Create" if creation_mode else "Edit"} NPC')
        
        self.minsize(1280, 720)

        self.transient(master)
        self.lift()
        self.focus_force()

        self.fields = {}

        for field in self.template["fields"]:
            ctk.CTkLabel(self, text=field["name"]).pack()
            value = npc.get(field["name"], field.get("default", ""))

            if field["name"] == "Faction":
                widget = ctk.CTkComboBox(self, values=get_faction_names())
                widget.set(value)
            elif field["type"] == "text":
                widget = ctk.CTkEntry(self)
                widget.insert(0, value)
            elif field["type"] == "longtext":
                frame = ctk.CTkFrame(self)
                text_widget = tk.Text(frame, height=6, wrap="word")
                text_widget.insert("1.0", value)
                text_widget.pack(fill="both", expand=True)
                widget = frame
                widget.text_widget = text_widget
            else:
                widget = ctk.CTkEntry(self)
                widget.insert(0, value)

            widget.pack(pady=2)
            self.fields[field["name"]] = widget

        save_button = ctk.CTkButton(self, text="Save", command=self.save_npc)
        save_button.pack(pady=5)

    def save_npc(self):
        for field in self.template["fields"]:
            widget = self.fields[field["name"]]
            if field["type"] in ["text", "choice"] or field["name"] == "Faction":
                self.npc[field["name"]] = widget.get()
            elif field["type"] == "longtext":
                self.npc[field["name"]] = widget.text_widget.get("1.0", "end").strip()

        self.saved = True
        self.destroy()
