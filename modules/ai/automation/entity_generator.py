import sqlite3
from typing import Dict, List, Any

from db.db import load_schema_from_json
from modules.ai.local_ai_client import LocalAIClient
from modules.ai.automation.prompt_builder import (
    build_entity_prompt,
    build_linked_entities_prompt,
)
from modules.ai.automation.response_parser import parse_ai_json
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_info, log_module_import
from modules.helpers.template_loader import load_template

log_module_import(__name__)


class EntityAutoGenerator:
    def __init__(self, *, db_path: str | None = None):
        self._db_path = db_path
        self._ai = LocalAIClient()

    def generate(self, entity_slug: str, count: int, user_prompt: str) -> List[Dict[str, Any]]:
        prompt = build_entity_prompt(entity_slug, count, user_prompt)
        response = self._ai.chat(
            [
                {"role": "system", "content": "You are a helpful RPG content generator."},
                {"role": "user", "content": prompt},
            ]
        )
        payload = parse_ai_json(response)
        items = self._normalize_payload(entity_slug, payload, count)
        return items

    def generate_with_names(
        self,
        entity_slug: str,
        names: List[str],
        user_prompt: str,
        parent_context: str,
    ) -> List[Dict[str, Any]]:
        if not names:
            return []
        prompt = build_linked_entities_prompt(entity_slug, names, user_prompt, parent_context)
        response = self._ai.chat(
            [
                {"role": "system", "content": "You are a helpful RPG content generator."},
                {"role": "user", "content": prompt},
            ]
        )
        payload = parse_ai_json(response)
        items = self._normalize_payload(entity_slug, payload, len(names), expected_names=names)
        return items

    def save(self, entity_slug: str, items: List[Dict[str, Any]]) -> None:
        self._ensure_schema(entity_slug)
        wrapper = GenericModelWrapper(entity_slug, db_path=self._db_path)
        for item in items:
            wrapper.save_item(item)
        log_info(
            f"Saved {len(items)} {entity_slug} item(s) via automation.",
            func_name="EntityAutoGenerator.save",
        )

    def _normalize_payload(
        self,
        entity_slug: str,
        payload: Any,
        count: int,
        *,
        expected_names: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            items = [payload]
        elif isinstance(payload, list):
            items = [p for p in payload if isinstance(p, dict)]
        else:
            raise RuntimeError("AI response did not contain objects")

        if count > 0:
            items = items[:count]

        template = load_template(entity_slug)
        fields = template.get("fields", [])
        typed_fields = {field.get("name"): field.get("type", "text") for field in fields}
        key_field = self._infer_key_field(entity_slug)

        normalized = []
        name_source = expected_names or []
        if name_source:
            items_by_name = {}
            for item in items:
                key = item.get(key_field)
                if isinstance(key, str):
                    items_by_name[key] = item
            for idx, name in enumerate(name_source, start=1):
                item = items_by_name.get(name, {})
                filled = self._fill_fields(item, typed_fields)
                if not filled.get(key_field):
                    filled[key_field] = name or f"{entity_slug.capitalize()} {idx}"
                normalized.append(filled)
            return normalized

        for idx, item in enumerate(items, start=1):
            filled = self._fill_fields(item, typed_fields)
            if not filled.get(key_field):
                filled[key_field] = f"{entity_slug.capitalize()} {idx}"
            normalized.append(filled)
        return normalized

    def _fill_fields(self, item: Dict[str, Any], typed_fields: Dict[str, str]) -> Dict[str, Any]:
        filled: Dict[str, Any] = {}
        for name, field_type in typed_fields.items():
            if name in item:
                filled[name] = item[name]
            else:
                filled[name] = [] if field_type in ("list", "list_longtext") else ""
        return filled

    def _infer_key_field(self, entity_slug: str) -> str:
        if entity_slug in {"scenarios", "books"}:
            return "Title"
        return "Name"

    def _ensure_schema(self, entity_slug: str) -> None:
        if not self._db_path:
            return
        schema = load_schema_from_json(entity_slug)
        if not schema:
            return
        pk = schema[0][0]
        cols = ",\n    ".join(f"{c} {t}" for c, t in schema)
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (entity_slug,),
            )
            if not cursor.fetchone():
                ddl = f"""
                CREATE TABLE IF NOT EXISTS {entity_slug} (
                    {cols},
                    PRIMARY KEY({pk})
                )"""
                cursor.execute(ddl)
            conn.commit()
        finally:
            conn.close()
