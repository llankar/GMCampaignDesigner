import re
import os
import json
import customtkinter as ctk
from tkinter import messagebox
from modules.helpers.text_helpers import format_longtext
from modules.generic.generic_model_wrapper import GenericModelWrapper


# Default formatting object.
default_formatting = {
    "bold": [],
    "italic": [],
    "underline": [],
    "left": [],
    "center": [],
    "right": []
}

def remove_emojis(text):
    emoji_pattern = re.compile("[" 
                               u"\U0001F600-\U0001F64F"  
                               u"\U0001F300-\U0001F5FF"  
                               u"\U0001F680-\U0001F6FF"  
                               u"\U0001F1E0-\U0001F1FF"  
                               u"\U00002702-\U000027B0"  
                               u"\U000024C2-\U0001F251"
                               "]+", flags=re.UNICODE)
    cleaned = emoji_pattern.sub(r'', text)
   #logging.debug("Emojis removed.")
    return cleaned

def import_formatted_scenario(text):
    # Remove emojis.
    cleaned_text = remove_emojis(text)
   #logging.info("Cleaned text (first 200 chars): %s", cleaned_text[:200])
    
    # --- Extract Basic Scenario Info ---
    title_match = re.search(r'^Scenario Title:\s*(.+)$', cleaned_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Unnamed Scenario"
   #logging.info("Parsed Title: %s", title)
    
    # Extract Introduction.
    intro_match = re.search(
        r'(?i)(?:^|\n)\s*Introduction\s*:?\s*(.*?)(?=\n\s*(?:Tied Player Characters:|Main Locations|📍 Main Locations|Key NPCs|NPCs))',
        cleaned_text,
        re.DOTALL
    )
    introduction = intro_match.group(1).strip() if intro_match else ""
   #logging.info("Parsed Introduction (first 100 chars): %s", introduction[:100])
    
    # --- Extract Places ---
    locations = []
    loc_split = re.split(r'(?mi)^\s*(?:Main Locations|📍 Main Locations).*$', cleaned_text, maxsplit=1)
    if len(loc_split) > 1:
        remainder = loc_split[1]
        npc_index = remainder.find("Key NPCs")
        if npc_index == -1:
            npc_index = remainder.find("NPCs")
        if npc_index >= 0:
            locs_text = remainder[:npc_index].strip()
        else:
            locs_text = remainder.strip()
       #logging.info("Extracted Places section (first 200 chars): %s", locs_text[:200])
        loc_entries = re.split(r'(?m)^\d+\.\s+', locs_text)
        for entry in loc_entries:
            entry = entry.strip()
            if not entry:
                continue
            lines = entry.splitlines()
            name_line = lines[0].strip()
            parts = re.split(r'\s*[-–]\s*', name_line)
            loc_name = parts[0].strip()
            description = ""
            current_section = None
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("Description:"):
                    current_section = "description"
                    description = line[len("Description:"):].strip()
                else:
                    if current_section == "description":
                        description += " " + line
            locations.append({
                "Name": loc_name,
                "Description": description.strip()
            })
    
    # --- Extract NPCs ---
    npcs = []
    npc_split = re.split(r'(?mi)^\s*(?:[^\w\s]*\s*)?(?:Key NPCs|NPCs)\s*:?.*$', cleaned_text, maxsplit=1)
    if len(npc_split) > 1:
        npc_text = npc_split[1].strip()
        #logging.info("Extracted NPCs section (first 200 chars): %s", npc_text[:200])
        npc_entries = re.split(r'(?m)^\d+\.\s+', npc_text)
        if npc_entries and not npc_entries[0].strip():
            npc_entries = npc_entries[1:]
        for entry in npc_entries:
            entry = entry.strip()
            if not entry:
                continue
            lines = entry.splitlines()
            header = lines[0].strip()
            if "–" in header:
                parts = re.split(r'\s*[-–]\s*', header)
                npc_name = parts[0].strip()
                npc_role = parts[1].strip() if len(parts) > 1 else ""
            else:
                npc_name = header
                npc_role = ""
            appearance = ""
            background = ""
            secret = ""
            current_section = None
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("Appearance:"):
                    current_section = "appearance"
                    appearance = line[len("Appearance:"):].strip()
                elif line.startswith("Background:"):
                    current_section = "background"
                    background = line[len("Background:"):].strip()
                elif line.startswith("Savage Fate Stats:"):
                    current_section = "stats"
                    secret = line[len("Savage Fate Stats:"):].strip()
                elif line.startswith("Stunt:"):
                    current_section = "stunt"
                    secret += " " + line[len("Stunt:"):].strip()
                else:
                    if current_section == "appearance":
                        appearance += " " + line
                    elif current_section == "background":
                        background += " " + line
                    elif current_section in ["stats", "stunt"]:
                        secret += " " + line
            combined_desc = (appearance + " " + background).strip()
            npc_obj = {
                "Name": npc_name,
                "Role": npc_role,
                "Description": {
                    "text": combined_desc,
                    "formatting": default_formatting
                },
                "Secret": {
                    "text": secret.strip(),
                    "formatting": default_formatting
                },
                "Factions": [],
                "Portrait": ""
            }
            npcs.append(npc_obj)
           #logging.info("Parsed NPC: %s; Role: %s; Desc snippet: %s; Secret snippet: %s", 
           #               npc_name, npc_role, combined_desc[:60], secret.strip()[:60])
    
    # --- Build Scenario Entity ---
    scenario_entity = {
        "Title": title,
        "Summary": {
            "text": introduction,
            "formatting": default_formatting
        },
        "Secrets": {
            "text": "",
            "formatting": default_formatting
        },
        "Places": [loc["Name"] for loc in locations],
        "NPCs": [npc["Name"] for npc in npcs]
    }
   #logging.info("Built scenario entity: %s", scenario_entity)
    
    # --- Save to the Database using Wrappers (append new records) ---
    scenario_wrapper = GenericModelWrapper("scenarios")
    places_wrapper = GenericModelWrapper("places")
    npcs_wrapper = GenericModelWrapper("npcs")
    
    existing_scenarios = scenario_wrapper.load_items()
    existing_places = places_wrapper.load_items()
    existing_npcs = npcs_wrapper.load_items()
    
    combined_scenarios = existing_scenarios + [scenario_entity]
    combined_places = existing_places + locations
    combined_npcs = existing_npcs + npcs
    
    scenario_wrapper.save_items(combined_scenarios)
    places_wrapper.save_items(combined_places)
    npcs_wrapper.save_items(combined_npcs)
    
   #logging.info("Scenario imported successfully using the database (appended to existing data)!")

# ─────────────────────────────────────────────────────────────────────────
# CLASS: ScenarioImportWindow
# A window that allows users to paste scenario text for import.
# ─────────────────────────────────────────────────────────────────────────
class ScenarioImportWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Import Formatted Scenario")
        self.geometry("600x600")
        
        instruction_label = ctk.CTkLabel(self, text="Paste your formatted scenario text below:")
        instruction_label.pack(pady=(10, 0), padx=10)
        
        # Create a CTkTextbox with a dark background and white text.
        self.scenario_textbox = ctk.CTkTextbox(self, wrap="word", height=400, fg_color="#2B2B2B", text_color="white")
        self.scenario_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        import_button = ctk.CTkButton(self, text="Import Scenario", command=self.import_scenario)
        import_button.pack(pady=(0, 10))
        
    def import_scenario(self):
        scenario_text = self.scenario_textbox.get("1.0", "end-1c")
        try:
            import_formatted_scenario(scenario_text)
            messagebox.showinfo("Success", "Scenario imported successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Error importing scenario:\n{str(e)}")
