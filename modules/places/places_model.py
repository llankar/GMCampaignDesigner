import json
import os

PLACES_PATH = os.path.join("data", "campaign1", "places.json")
TEMPLATE_PATH = os.path.join("data", "campaign1", "place_template.json")

def load_places():
    if not os.path.exists(PLACES_PATH):
        return []
    with open(PLACES_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_places(places):
    os.makedirs(os.path.dirname(PLACES_PATH), exist_ok=True)
    with open(PLACES_PATH, 'w', encoding='utf-8') as file:
        json.dump(places, file, indent=4, ensure_ascii=False)

def load_template():
    if not os.path.exists(TEMPLATE_PATH):
        return {"fields": [
            {"name": "Name", "type": "text", "default": ""},
            {"name": "Description", "type": "longtext", "default": ""},
            {"name": "Cool Elements", "type": "longtext", "default": ""},
            {"name": "Clues", "type": "longtext", "default": ""}
        ]}
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {"fields": [
                {"name": "Name", "type": "text", "default": ""},
                {"name": "Description", "type": "longtext", "default": ""},
                {"name": "Cool Elements", "type": "longtext", "default": ""},
                {"name": "Clues", "type": "longtext", "default": ""}
            ]}