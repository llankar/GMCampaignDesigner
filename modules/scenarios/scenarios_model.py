
import json
import os

DATA_PATH = os.path.join("data", "campaign1", "scenarios.json")
TEMPLATE_PATH = os.path.join("data", "campaign1", "scenarios_template.json")

def load_scenarios():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_scenarios(items):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as file:
        json.dump(items, file, indent=4, ensure_ascii=False)

def load_template():
    if not os.path.exists(TEMPLATE_PATH):
        return {"fields": [
    {
        "name": "Name",
        "type": "text"
    },
    {
        "name": "Places",
        "type": "choice",
        "options": [
            "(linked to places list)"
        ]
    },
    {
        "name": "NPCs",
        "type": "choice",
        "options": [
            "(linked to npcs list)"
        ]
    },
    {
        "name": "Secrets",
        "type": "longtext"
    }
]}
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {"fields": [
    {
        "name": "Name",
        "type": "text"
    },
    {
        "name": "Places",
        "type": "choice",
        "options": [
            "(linked to places list)"
        ]
    },
    {
        "name": "NPCs",
        "type": "choice",
        "options": [
            "(linked to npcs list)"
        ]
    },
    {
        "name": "Secrets",
        "type": "longtext"
    }
]}
