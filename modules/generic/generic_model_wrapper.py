import sqlite3
import json
from db.db import get_connection, load_schema_from_json
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

class GenericModelWrapper:
    def __init__(self, entity_type, db_path=None):
        self.entity_type = entity_type
        # Assume your table name is the same as the entity type (e.g., "npcs")
        self.table = entity_type
        self._db_path = db_path

    def _get_connection(self):
        if self._db_path:
            return sqlite3.connect(self._db_path)
        return get_connection()

    def _deserialize_row(self, row):
        item = {}
        for key in row.keys():
            value = row[key]
            if isinstance(value, str) and value.strip().startswith(("{", "[", "\"")):
                try:
                    item[key] = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    item[key] = value
            else:
                item[key] = value
        return item

    def _infer_key_field(self, key_field=None):
        if key_field:
            return key_field
        if self.entity_type in {"scenarios", "books"}:
            return "Title"
        return "Name"

    def load_items(self):
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries.
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {self.table}")
        rows = cursor.fetchall()
        items = [self._deserialize_row(row) for row in rows]
        conn.close()
        return items

    def load_item_by_key(self, key_value, key_field=None):
        key_field = self._infer_key_field(key_field)
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self.table} WHERE {key_field} = ?",
                (key_value,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._deserialize_row(row)
        finally:
            conn.close()


    def _ensure_schema(self, cursor, items):
        """Ensure that any new fields present in ``items`` exist in the table."""
        cursor.execute(f"PRAGMA table_info({self.table})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Attempt to load template information for better type inference
        try:
            template_schema = {col: typ for col, typ in load_schema_from_json(self.table)}
        except Exception:
            template_schema = {}

        for item in items:
            for key, value in item.items():
                if key in existing_columns:
                    continue

                column_type = template_schema.get(key)
                if not column_type:
                    if isinstance(value, bool):
                        column_type = "BOOLEAN"
                    elif isinstance(value, int):
                        column_type = "INTEGER"
                    elif isinstance(value, float):
                        column_type = "REAL"
                    elif isinstance(value, (list, dict)):
                        column_type = "TEXT"
                    elif isinstance(value, str) or value is None:
                        column_type = "TEXT"
                    else:
                        column_type = "TEXT"

                try:
                    cursor.execute(
                        f"ALTER TABLE {self.table} ADD COLUMN {key} {column_type}"
                    )
                    existing_columns.add(key)
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" in str(exc).lower():
                        existing_columns.add(key)
                    else:
                        raise

        return existing_columns

    def save_items(self, items, *, replace=True):
        conn = self._get_connection()
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()

        try:
            existing_columns = self._ensure_schema(cursor, items)

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
                keys = [key for key in item.keys() if key in existing_columns]
                values = []
                for key in keys:
                    val = item[key]
                    if isinstance(val, (list, dict)):
                        val = json.dumps(val)
                    values.append(val)
                placeholders = ", ".join("?" for _ in keys)
                cols = ", ".join(keys)
                sql = f"INSERT OR REPLACE INTO {self.table} ({cols}) VALUES ({placeholders})"
                if keys:
                    cursor.execute(sql, values)

            # Gestion du cas de suppression :
            # On construit la liste des identifiants uniques présents dans les items
            unique_ids = [item[unique_field] for item in items if unique_field in item]

            if replace:
                if unique_ids:
                    placeholders = ", ".join("?" for _ in unique_ids)
                    delete_sql = f"DELETE FROM {self.table} WHERE {unique_field} NOT IN ({placeholders})"
                    cursor.execute(delete_sql, unique_ids)
                else:
                    # S'il n'y a aucun item, supprimer tous les enregistrements de la table
                    delete_sql = f"DELETE FROM {self.table}"
                    cursor.execute(delete_sql)

            conn.commit()
        finally:
            conn.close()

    def save_item(self, item, *, key_field=None):
        if not isinstance(item, dict):
            raise TypeError("item must be a dictionary")

        conn = self._get_connection()
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()

        try:
            existing_columns = self._ensure_schema(cursor, [item])
            key_field = self._infer_key_field(key_field)

            keys = [key for key in item.keys() if key in existing_columns]
            values = []
            for key in keys:
                val = item[key]
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                values.append(val)

            if not keys:
                return

            placeholders = ", ".join("?" for _ in keys)
            cols = ", ".join(keys)
            sql = f"INSERT OR REPLACE INTO {self.table} ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            conn.commit()
        finally:
            conn.close()
