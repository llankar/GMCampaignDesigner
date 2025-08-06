import sqlite3
import json
from db.db import get_connection

class GenericModelWrapper:
    def __init__(self, entity_type):
        self.entity_type = entity_type
        # Assume your table name is the same as the entity type (e.g., "npcs")
        self.table = entity_type  

    def load_items(self):
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries.
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {self.table}")
        rows = cursor.fetchall()
        items = []
        for row in rows:
            item = {}
            for key in row.keys():
                value = row[key]
                # Decode only likely JSON: starts with {, [, or "
                if isinstance(value, str) and value.strip().startswith(("{", "[", "\"")):
                    try:
                        item[key] = json.loads(value)
                    except (TypeError, json.JSONDecodeError):
                        item[key] = value
                else:
                    item[key] = value
            items.append(item)
        conn.close()
        return items


    def save_items(self, items):
        conn = get_connection()
        cursor = conn.cursor()
        
        # Détermine le champ unique à utiliser
        if items:
            sample_item = items[0]
            if "Name" in sample_item:
                unique_field = "Name"
            elif "Title" in sample_item:
                unique_field = "Title"
            else:
                unique_field = list(sample_item.keys())[0]
        else:
            unique_field = "Name"  # Valeur par défaut si la liste est vide

        # Insertion ou mise à jour (INSERT OR REPLACE)
        for item in items:
            keys = list(item.keys())
            values = []
            for key in keys:
                val = item[key]
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                values.append(val)
            placeholders = ", ".join("?" for _ in keys)
            cols = ", ".join(keys)
            sql = f"INSERT OR REPLACE INTO {self.table} ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, values)
        
        # Gestion du cas de suppression :
        # On construit la liste des identifiants uniques présents dans les items
        unique_ids = [item[unique_field] for item in items if unique_field in item]
        
        if unique_ids:
            placeholders = ", ".join("?" for _ in unique_ids)
            delete_sql = f"DELETE FROM {self.table} WHERE {unique_field} NOT IN ({placeholders})"
            cursor.execute(delete_sql, unique_ids)
        else:
            # S'il n'y a aucun item, supprimer tous les enregistrements de la table
            delete_sql = f"DELETE FROM {self.table}"
            cursor.execute(delete_sql)
        
        conn.commit()
        conn.close()
