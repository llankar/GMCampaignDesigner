import json
import os

def load_template(entity_name):
    with open(f"modules/{entity_name}/{entity_name}_template.json", "r", encoding="utf-8") as f:
        return json.load(f)