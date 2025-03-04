import customtkinter as ctk
import tkinter as tk
from modules.places.places_model import load_places
from modules.pnjs.pnjs_model import load_npcs
from modules.helpers.selection_dialog import SelectionDialog

def get_place_names():
    return [place["Name"] for place in load_places()]

def get_npc_names():
    return [npc["Name"] for npc in load_npcs()]

class EditScenarioWindow(ctk.CTkToplevel):
    def __init__(self, master, scenario, creation_mode=False):
        super().__init__(master)
        self.scenario = scenario
        self.saved = False

        self.title(f'{"Create" if creation_mode else "Edit"} Scenario')
        
        self.minsize(1280, 720)

        self.transient(master)
        self.lift()
        self.focus_force()

        ctk.CTkLabel(self, text="Name").pack()
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, scenario.get("Name", ""))
        self.name_entry.pack(pady=5)

        ctk.CTkLabel(self, text="Places").pack()
        self.places_listbox = tk.Listbox(self, height=5)
        for place in scenario.get("Places", []):
            self.places_listbox.insert(tk.END, place)
        self.places_listbox.pack()
        ctk.CTkButton(self, text="Add Place", command=self.add_place).pack(pady=5)

        ctk.CTkLabel(self, text="NPCs").pack()
        self.npcs_listbox = tk.Listbox(self, height=5)
        for npc in scenario.get("NPCs", []):
            self.npcs_listbox.insert(tk.END, npc)
        self.npcs_listbox.pack()
        ctk.CTkButton(self, text="Add NPC", command=self.add_npc).pack(pady=5)

        ctk.CTkLabel(self, text="Secrets").pack()
        self.secrets_text = tk.Text(self, height=6, wrap="word")
        self.secrets_text.insert("1.0", scenario.get("Secrets", ""))
        self.secrets_text.pack(pady=5, fill="both", expand=True)

        save_button = ctk.CTkButton(self, text="Save", command=self.save_scenario)
        save_button.pack(pady=5)

    def add_place(self):
        dialog = SelectionDialog(self, "Add Place", "Choose a place:", get_place_names())
        self.wait_window(dialog)
        if dialog.result:
            self.places_listbox.insert(tk.END, dialog.result)

    def add_npc(self):
        dialog = SelectionDialog(self, "Add NPC", "Choose an NPC:", get_npc_names())
        self.wait_window(dialog)
        if dialog.result:
            self.npcs_listbox.insert(tk.END, dialog.result)

    def save_scenario(self):
        self.scenario["Name"] = self.name_entry.get()
        self.scenario["Places"] = list(self.places_listbox.get(0, tk.END))
        self.scenario["NPCs"] = list(self.npcs_listbox.get(0, tk.END))
        self.scenario["Secrets"] = self.secrets_text.get("1.0", "end").strip()

        self.saved = True
        self.destroy()