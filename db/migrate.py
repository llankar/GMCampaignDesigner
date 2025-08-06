# migrate.py
import json
import os
import sqlite3
from db import get_connection, initialize_db

def migrate_table(json_file, table, columns):
    if not os.path.exists(json_file):
        print(f"{json_file} does not exist.")
        return
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for entry in data:
        values = []
        for col in columns:
            val = entry.get(col, None)
            # For lists or dicts, store them as JSON strings
            if isinstance(val, (list, dict)):
                val = json.dumps(val)
            values.append(val)
        placeholders = ", ".join("?" * len(columns))
        cols_joined = ", ".join(columns)
        sql = f"INSERT OR REPLACE INTO {table} ({cols_joined}) VALUES ({placeholders})"
        cursor.execute(sql, values)
    
    conn.commit()
    conn.close()
    print(f"Migrated data from {json_file} to {table}")

if __name__ == "__main__":
    initialize_db()
    
    # Migrate NPCs (fields based on npcs_template.json)
    migrate_table("data/npcs.json", "npcs", ["Name", "Role", "Description", "Secret", "Factions", "Objects", "Portrait"])
    
    # Migrate Scenarios
    migrate_table("data/scenarios.json", "scenarios", ["Title", "Summary", "Secrets", "Places", "NPCs", "Objects"])
    
    # Migrate Factions
    migrate_table("data/factions.json", "factions", ["Name", "Description", "Secrets"])
    
    # Migrate Places
    migrate_table("data/places.json", "places", ["Name", "Description", "NPCs"])
    
    # Migrate Objects
    migrate_table("data/objects.json", "objects", ["Name", "Description", "Secrets", "Portrait"])
