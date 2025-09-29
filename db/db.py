# db.py
import sqlite3
import os
import re
import platform
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.template_loader import (
    load_template,
    list_known_entities,
    sync_campaign_template,
)
import logging
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

# Map our JSON “type” names to SQLite types
_SQLITE_TYPE = {
    "text":     "TEXT",
    "longtext": "TEXT",
    "boolean":  "BOOLEAN",
    "list":     "TEXT",  # we’ll store lists as JSON strings
    "file":     "TEXT",
    "float":    "REAL",
    "int":      "INTEGER",
    "audio":    "TEXT",
}

def load_schema_from_json(entity_name):
    """Load merged template for entity (campaign-local preferred) and return SQL schema."""
    tmpl = load_template(entity_name)
    schema = []
    for field in tmpl.get("fields", []):
        name = field.get("name")
        jtype = field.get("type", "text")
        if not name:
            continue
        schema.append((name, _SQLITE_TYPE.get(jtype, "TEXT")))
    return schema


def _ensure_campaign_templates():
    """Ensure campaign templates exist and are kept in sync with defaults."""
    db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db") or "default_campaign.db"
    camp_dir = os.path.abspath(os.path.dirname(db_path))
    tpl_dir = os.path.join(camp_dir, "templates")
    try:
        os.makedirs(tpl_dir, exist_ok=True)
    except Exception:
        pass

    for entity in list_known_entities():
        default_tpl = os.path.join("modules", entity, f"{entity}_template.json")
        if not os.path.exists(default_tpl):
            continue
        try:
            sync_campaign_template(entity)
        except Exception:
            # Individual template sync issues should not block DB startup.
            continue


def _ensure_schema_for_entity(cursor, entity):
    schema = load_schema_from_json(entity)
    if not schema:
        return
    pk = schema[0][0]
    cols = ",\n    ".join(f"{c} {t}" for c, t in schema)

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (entity,),
    )
    if not cursor.fetchone():
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {entity} (
            {cols},
            PRIMARY KEY({pk})
        )"""
        cursor.execute(ddl)
        return

    cursor.execute(f"PRAGMA table_info({entity})")
    rows = cursor.fetchall()
    existing = {row[1] for row in rows}
    for col, typ in schema:
        if col in existing:
            continue
        cursor.execute(
            f"ALTER TABLE {entity} ADD COLUMN {col} {typ}"
        )

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
    _ensure_campaign_templates()
    conn   = get_connection()
    cursor = conn.cursor()

    # Create tables if missing
    for entity in list_known_entities():
        try:
            _ensure_schema_for_entity(cursor, entity)
        except Exception as exc:
            logging.warning("Failed to ensure schema for %s: %s", entity, exc)

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
    for entity in list_known_entities():
        try:
            _ensure_schema_for_entity(cursor, entity)
        except Exception as exc:
            logging.warning("Failed to update schema for %s: %s", entity, exc)

    conn.commit()

def ensure_entity_schema(entity: str):
    """Ensure the SQLite schema for ``entity`` exists and matches its template."""

    conn = get_connection()
    cursor = conn.cursor()
    try:
        _ensure_campaign_templates()
        _ensure_schema_for_entity(cursor, entity)
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    initialize_db()
    print("Database initialized.")


