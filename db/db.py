# db.py
import sqlite3
import os
import re
import platform
from typing import Dict, List, Optional
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


def _ensure_campaign_metadata_tables(cursor):
    """Create metadata tables that track supported systems and settings."""

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_systems (
            slug TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            default_formula TEXT,
            supported_faces_json TEXT,
            analyzer_config_json TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )


_DEFAULT_SYSTEMS: List[Dict[str, Optional[str]]] = [
    {
        "slug": "d20",
        "label": "D20 System",
        "default_formula": "1d20 + mod",
        "supported_faces_json": "[4,6,8,10,12,20]",
        "analyzer_config_json": None,
    },
    {
        "slug": "2d20",
        "label": "2d20 System",
        "default_formula": "2d20kh1 + mod",
        "supported_faces_json": "[20]",
        "analyzer_config_json": None,
    },
    {
        "slug": "savage_fate",
        "label": "Savage Fate",
        "default_formula": "1dF + mod",
        "supported_faces_json": '["F",4,6,8,10,12]',
        "analyzer_config_json": None,
    },
]


def _ensure_default_systems(cursor):
    """Populate the systems catalog and default campaign settings when needed."""

    cursor.execute("SELECT COUNT(*) FROM campaign_systems")
    count = cursor.fetchone()[0]
    if not count:
        cursor.executemany(
            """
            INSERT INTO campaign_systems (
                slug, label, default_formula, supported_faces_json, analyzer_config_json
            ) VALUES (:slug, :label, :default_formula, :supported_faces_json, :analyzer_config_json)
            """,
            _DEFAULT_SYSTEMS,
        )

    cursor.execute(
        "SELECT value FROM campaign_settings WHERE key = ?",
        ("system_slug",),
    )
    row = cursor.fetchone()
    if row is None:
        default_slug = _DEFAULT_SYSTEMS[0]["slug"]
        cursor.execute(
            "INSERT OR REPLACE INTO campaign_settings (key, value) VALUES (?, ?)",
            ("system_slug", default_slug),
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

    _ensure_campaign_metadata_tables(cursor)
    _ensure_default_systems(cursor)

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


def get_campaign_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch a campaign setting value."""

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT value FROM campaign_settings WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        return row[0] if row is not None else default
    finally:
        conn.close()


def set_campaign_setting(key: str, value: Optional[str]) -> None:
    """Create or update a campaign setting value."""

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO campaign_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_selected_system_slug(default: Optional[str] = None) -> Optional[str]:
    """Return the slug of the currently selected campaign system."""

    return get_campaign_setting("system_slug", default)


def set_selected_system_slug(slug: str) -> None:
    """Persist the slug for the currently selected campaign system."""

    set_campaign_setting("system_slug", slug)

if __name__ == "__main__":
    initialize_db()
    print("Database initialized.")


