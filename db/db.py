# db.py
import sqlite3
import os
import json
import re
import platform
from modules.helpers.config_helper import ConfigHelper
import logging

# Map our JSON “type” names to SQLite types
_SQLITE_TYPE = {
    "text":     "TEXT",
    "longtext": "TEXT",
    "boolean":  "BOOLEAN",
    "list":     "TEXT", # we’ll store lists as JSON strings
    "file":     "TEXT",
    "float":    "REAL",
}

def load_schema_from_json(entity_name):
    """
    Opens PROJECT_ROOT/modules/<entity_name>/<entity_name>_template.json
    and returns [(col_name, sql_type), …].
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    json_path    = os.path.join(
        project_root,
        "modules",
        entity_name,
        f"{entity_name}_template.json"
    )
    with open(json_path, encoding="utf-8") as f:
        tmpl = json.load(f)

    schema = []
    for field in tmpl["fields"]:
        name = field["name"]
        jtype = field["type"]
        schema.append((name, _SQLITE_TYPE.get(jtype, "TEXT")))
    return schema

def get_connection():
    raw_db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db").strip()
    is_windows_style_path = re.match(r"^[a-zA-Z]:[\\/\\]", raw_db_path)

    if platform.system() != "Windows" and is_windows_style_path:
        drive_letter = raw_db_path[0].upper()
        subpath = raw_db_path[2:].lstrip("/\\").replace("\\", "/")
        if subpath.lower().startswith("synologydrive/"):
            subpath = subpath[len("synologydrive/"):]
        synology_base = "/volume1/homes/llankar/Drive"
        DB_PATH = os.path.join(synology_base, subpath)
    else:
        DB_PATH = raw_db_path if os.path.exists(raw_db_path) else os.path.abspath(os.path.normpath(raw_db_path))

    return sqlite3.connect(DB_PATH)

def initialize_db():
    conn   = get_connection()
    cursor = conn.cursor()

    # Create tables if missing
    for table in ["pcs","npcs","scenarios","factions","places","objects","informations","clues", "creatures", "maps"]:
        schema = load_schema_from_json(table)
        pk = schema[0][0]
        cols_sql = ",\n    ".join(f"{col} {typ}" for col,typ in schema)
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            {cols_sql},
            PRIMARY KEY({pk})
        )"""
        cursor.execute(ddl)

    # Add any new columns for existing tables
    update_table_schema(conn, cursor)

    conn.commit()
    conn.close()

def update_table_schema(conn, cursor):
    """
    For each entity:
    - If its table is missing, CREATE it from modules/<entity>/<entity>_template.json
    - Else, ALTER it to add any new columns defined in that same JSON
    """
    entities = [
        "npcs",
        "scenarios",
        "factions",
        "places",
        "objects",
        "creatures",      # new one
        "informations",
        "clues",
        "pcs",
        "maps"
    ]

    for ent in entities:
        schema = load_schema_from_json(ent)
        pk     = schema[0][0]
        cols   = ",\n    ".join(f"{c} {t}" for c, t in schema)

        # 1) does table exist?
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (ent,)
        )
        if not cursor.fetchone():
            # create the whole table
            ddl = f"""
            CREATE TABLE {ent} (
                {cols},
                PRIMARY KEY({pk})
            )"""
            cursor.execute(ddl)
        else:
            # just add any missing columns
            cursor.execute(f"PRAGMA table_info({ent})")
            rows = cursor.fetchall()
            # second column is the column name
            existing = {row[1] for row in rows}
            for col, typ in schema:
                if col not in existing:
                    cursor.execute(
                        f"ALTER TABLE {ent} ADD COLUMN {col} {typ}"
                    )

    conn.commit()

if __name__ == "__main__":
    initialize_db()
    print("Database initialized.")