import json
import os

NPCS_PATH = os.path.join("data", "campaign1", "npcs.json")
TEMPLATE_PATH = os.path.join("data", "campaign1", "pnj_template.json")

def load_npcs():
    if not os.path.exists(NPCS_PATH):
        return []
    with open(NPCS_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_npcs(npcs):
    os.makedirs(os.path.dirname(NPCS_PATH), exist_ok=True)
    with open(NPCS_PATH, 'w', encoding='utf-8') as file:
        json.dump(npcs, file, indent=4, ensure_ascii=False)

def load_template():
    if not os.path.exists(TEMPLATE_PATH):
        return {"fields": [{"name": "Name", "type": "text", "default": ""}]}
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {"fields": [{"name": "Name", "type": "text", "default": ""}]}

def get_npc_by_id(npc_list, npc_id):
    for npc in npc_list:
        if npc["id"] == npc_id:
            return npc
    return None
