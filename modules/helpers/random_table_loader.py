import json
import os
from typing import Dict, Iterable, List, Optional, Tuple

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_module_import

log_module_import(__name__)


PLOT_TWIST_TABLE_ID = "universal_plot_twists"


class RandomTableLoader:
    """Load and validate random tables from a JSON file or directory."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or self.default_data_path()
        self.categories: List[dict] = []
        self.tables: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    @staticmethod
    def default_data_path() -> str:
        """Return the preferred random tables path.

        The loader looks for a directory first so tables can be split across
        multiple files. If no directory is found, it falls back to a single
        JSON file either in the app or the current campaign.
        """

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        local_dir = os.path.join(project_root, "static", "data", "random_tables")
        local_file = os.path.join(project_root, "static", "data", "random_tables.json")

        campaign_dir = os.path.join(ConfigHelper.get_campaign_dir(), "static", "data", "random_tables")
        campaign_file = os.path.join(ConfigHelper.get_campaign_dir(), "static", "data", "random_tables.json")

        if os.path.isdir(local_dir):
            return local_dir
        if os.path.exists(local_file):
            return local_file
        if os.path.isdir(campaign_dir):
            return campaign_dir
        if os.path.exists(campaign_file):
            return campaign_file
        return local_file

    # ------------------------------------------------------------------
    def load(self) -> Dict[str, dict]:
        self.categories = []
        self.tables = {}

        for source in self._iter_sources(self.base_path):
            data = self._read_source(source)
            if not data:
                continue
            system = self._coerce_str(data.get("system"))
            biome = self._coerce_str(data.get("biome"))
            theme = self._coerce_str(data.get("theme"))

            for raw_category in data.get("categories") or []:
                cat_id = self._coerce_id(raw_category.get("id") or raw_category.get("name") or f"category_{len(self.categories)+1}")
                category = self._get_or_create_category(cat_id, raw_category.get("name"))

                for raw_table in raw_category.get("tables") or []:
                    normalized = self._normalize_table(raw_table, category["id"], system, biome, theme, source)
                    if not normalized:
                        continue
                    if normalized["id"] in self.tables:
                        log_info(
                            f"Duplicate table id '{normalized['id']}' found in {source}; keeping first occurrence",
                            func_name="RandomTableLoader.load",
                        )
                        continue
                    self.tables[normalized["id"]] = normalized
                    category["tables"].append(normalized)

        self.categories = list(self.categories)
        return {"categories": self.categories, "tables": self.tables}

    def get_table(self, table_id: str) -> Optional[dict]:
        return self.tables.get(table_id)

    def list_tables(self) -> List[dict]:
        return list(self.tables.values())

    # ------------------------------------------------------------------
    def _iter_sources(self, path: str) -> Iterable[str]:
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if not name.lower().endswith(".json"):
                    continue
                yield os.path.join(path, name)
        elif os.path.exists(path):
            yield path
        else:
            log_info(f"Random tables path not found: {path}", func_name="RandomTableLoader._iter_sources")

    def _read_source(self, source: str) -> dict:
        try:
            with open(source, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                log_info(f"Skipping random table file without object root: {source}", func_name="RandomTableLoader._read_source")
                return {}
            return data
        except Exception as exc:
            log_info(f"Unable to read random tables from {source}: {exc}", func_name="RandomTableLoader._read_source")
            return {}

    def _get_or_create_category(self, cat_id: str, name: Optional[str]) -> dict:
        for category in self.categories:
            if category.get("id") == cat_id:
                return category
        category = {"id": cat_id, "name": name or cat_id.title(), "tables": []}
        self.categories.append(category)
        return category

    def _normalize_table(
        self, table: dict, category_id: str, system: Optional[str], biome: Optional[str], theme: Optional[str], source: str
    ) -> Optional[dict]:
        title = self._coerce_str(table.get("title") or table.get("name"))
        table_id = self._coerce_id(table.get("id") or title or f"table_{len(self.tables)+1}")
        dice = self._coerce_str(table.get("dice"))
        entries = table.get("entries") or []

        if not title or not dice or not entries:
            log_info(
                f"Skipping table '{table_id}' in {source} because it is missing required fields (name/title, dice, entries)",
                func_name="RandomTableLoader._normalize_table",
            )
            return None

        normalized_entries = self._normalize_entries(entries)
        return {
            "id": table_id,
            "title": title,
            "dice": dice,
            "entries": normalized_entries,
            "description": self._coerce_str(table.get("description")) or "",
            "tags": [self._coerce_str(tag) for tag in (table.get("tags") or []) if self._coerce_str(tag)],
            "category": category_id,
            "system": self._coerce_str(table.get("system") or system),
            "biome": self._coerce_str(table.get("biome") or biome),
            "theme": self._coerce_str(table.get("theme") or theme),
            "source": source,
        }

    def _normalize_entries(self, entries: List[dict]) -> List[dict]:
        normalized: List[dict] = []
        for idx, raw in enumerate(entries, start=1):
            result = self._coerce_str(raw.get("result") or raw.get("text") or f"Entry {idx}")
            rng = raw.get("range")
            if rng is None and "min" in raw and "max" in raw:
                rng = f"{raw.get('min')}-{raw.get('max')}"
            min_val, max_val = self._parse_range(str(rng) if rng is not None else str(idx))
            normalized.append(
                {
                    "min": min_val,
                    "max": max_val,
                    "result": result,
                    "tags": [self._coerce_str(tag) for tag in (raw.get("tags") or []) if self._coerce_str(tag)],
                }
            )
        return normalized

    def _parse_range(self, range_text: str) -> Tuple[int, int]:
        text = (range_text or "").strip()
        if "-" in text:
            start, end = text.split("-", 1)
            try:
                return int(start), int(end)
            except ValueError:
                return 1, 1
        try:
            value = int(text)
            return value, value
        except ValueError:
            return 1, 1

    @staticmethod
    def _coerce_id(value: str) -> str:
        text = str(value or "").strip()
        return text.replace(" ", "_") if text else "table"

    @staticmethod
    def _coerce_str(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


def plot_twist_data_path() -> str:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(project_root, "static", "data", "random_tables", "Plot twists.json")


def load_plot_twist_table(table_id: str = PLOT_TWIST_TABLE_ID) -> Optional[dict]:
    loader = RandomTableLoader(plot_twist_data_path())
    data = loader.load()
    table = (data.get("tables") or {}).get(table_id)
    if table:
        return table
    tables = list((data.get("tables") or {}).values())
    return tables[0] if tables else None


__all__ = ["RandomTableLoader", "PLOT_TWIST_TABLE_ID", "plot_twist_data_path", "load_plot_twist_table"]
