import json
import os

DATA_FILE = "clues.json"

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save(items):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
