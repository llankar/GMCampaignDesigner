import json
import os

FACTIONS_PATH = os.path.join("data", "campaign1", "factions.json")
TEMPLATE_PATH = os.path.join("data", "campaign1", "factions_template.json")

def load_factions():
    if not os.path.exists(FACTIONS_PATH):
        return []
    with open(FACTIONS_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_factions(factions):
    os.makedirs(os.path.dirname(FACTIONS_PATH), exist_ok=True)
    with open(FACTIONS_PATH, 'w', encoding='utf-8') as file:
        json.dump(factions, file, indent=4, ensure_ascii=False)

def load_template():
    if not os.path.exists(TEMPLATE_PATH):
        return {"fields": [
            {"name": "Name", "type": "text", "default": ""},
            {"name": "Description", "type": "longtext", "default": ""},
            {"name": "Secrets", "type": "longtext", "default": ""}
        ]}
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {"fields": [
                {"name": "Name", "type": "text", "default": ""},
                {"name": "Description", "type": "longtext", "default": ""},
                {"name": "Secrets", "type": "longtext", "default": ""}
            ]}