import sqlite3
import json
from db.db import get_connection, load_schema_from_json
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

class GenericModelWrapper:
    def __init__(self, entity_type):
        self.entity_type = entity_type
        # Assume your table name is the same as the entity type (e.g., "npcs")
        self.table = entity_type  

    def _decode_row(self, row):
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
        return item

    def load_items(self):
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries.
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {self.table}")
        rows = cursor.fetchall()
        items = [self._decode_row(row) for row in rows]
        conn.close()
        return items

    def get_item_by_field(self, field, value):
        if not field.replace("_", "").isalnum():
            raise ValueError("Field name must be alphanumeric or underscore-only.")

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.table} WHERE {field} = ? LIMIT 1",
            (value,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return self._decode_row(row)


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

    def _determine_unique_field(self, sample_item):
        if not sample_item:
            return "Name"

        preferred = ("Name", "Title", "id", "ID", "uuid", "UUID")
        for candidate in preferred:
            if candidate in sample_item:
                return candidate

        return next(iter(sample_item.keys()))

    def save_items(self, items):
        conn = get_connection()
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()

        try:
            existing_columns = self._ensure_schema(cursor, items)

            # Détermine le champ unique à utiliser
            if items:
                sample_item = items[0]
                unique_field = self._determine_unique_field(sample_item)
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

    def upsert_item(self, item):
        if not item:
            raise ValueError("Cannot upsert an empty item.")

        conn = get_connection()
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()

        try:
            existing_columns = self._ensure_schema(cursor, [item])
            unique_field = self._determine_unique_field(item)

            if unique_field not in item:
                raise KeyError(
                    f"Unique field '{unique_field}' is required in item for upsert."
                )

            keys = [key for key in item.keys() if key in existing_columns]
            values = []
            for key in keys:
                val = item[key]
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                values.append(val)

            if not keys:
                raise ValueError("Item does not contain any known columns to upsert.")

            placeholders = ", ".join("?" for _ in keys)
            cols = ", ".join(keys)
            sql = f"INSERT OR REPLACE INTO {self.table} ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            conn.commit()
        finally:
            conn.close()
