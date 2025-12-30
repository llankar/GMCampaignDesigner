import json
from typing import Any, Dict, List

from modules.ai.automation.entity_generator import EntityAutoGenerator
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_info, log_module_import
from modules.helpers.template_loader import load_template

log_module_import(__name__)


class AutoGenerationService:
    def __init__(self, *, db_path: str | None = None):
        self._generator = EntityAutoGenerator(db_path=db_path)
        self._db_path = db_path

    def generate_and_save(
        self,
        entity_slug: str,
        count: int,
        user_prompt: str,
        *,
        include_linked: bool = True,
    ) -> List[Dict[str, Any]]:
        items = self._generator.generate(entity_slug, count, user_prompt)
        self._generator.save(entity_slug, items)

        if include_linked:
            for item in items:
                self._generate_linked_entities(entity_slug, item, user_prompt)
        return items

    def generate_story_arc_and_save(
        self,
        scenario_count: int,
        user_prompt: str,
        *,
        include_linked: bool = True,
    ) -> List[Dict[str, Any]]:
        arc = self._generator.generate_story_arc(scenario_count, user_prompt)
        items = self._generator.save_story_arc(arc)
        if include_linked:
            for item in items:
                self._generate_linked_entities("scenarios", item, user_prompt)
        return items

    def _generate_linked_entities(self, entity_slug: str, item: Dict[str, Any], user_prompt: str) -> None:
        template = load_template(entity_slug)
        fields = template.get("fields", [])
        linked_fields = [
            field for field in fields
            if field.get("type") in ("list", "list_longtext") and field.get("linked_type")
        ]
        if not linked_fields:
            return

        parent_context = self._build_parent_context(entity_slug, item)

        for field in linked_fields:
            field_name = field.get("name")
            linked_type = field.get("linked_type")
            if not field_name or not linked_type:
                continue
            linked_slug = self._slugify(linked_type)
            names = self._extract_names(item.get(field_name))
            if not names:
                continue

            wrapper = GenericModelWrapper(linked_slug, db_path=self._db_path)
            missing = [name for name in names if not wrapper.load_item_by_key(name)]
            if not missing:
                continue

            generated = self._generator.generate_with_names(
                linked_slug,
                missing,
                user_prompt,
                parent_context,
            )
            if generated:
                self._generator.save(linked_slug, generated)
                log_info(
                    f"Auto-generated {len(generated)} linked {linked_slug} for {entity_slug}.",
                    func_name="AutoGenerationService._generate_linked_entities",
                )

    def _extract_names(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
            return [part.strip() for part in raw.split(",") if part.strip()]
        return []

    def _build_parent_context(self, entity_slug: str, item: Dict[str, Any]) -> str:
        key_field = "Title" if entity_slug in {"scenarios", "books"} else "Name"
        title = item.get(key_field, "")
        summary = item.get("Summary", "") or item.get("Description", "")
        return f"Parent {entity_slug}: {title}\nSummary: {summary}".strip()

    def _slugify(self, label: str) -> str:
        return label.strip().lower().replace(" ", "_")
