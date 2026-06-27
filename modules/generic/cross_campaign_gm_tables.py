"""Helpers for cross-campaign GM virtual table bundle data."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

from modules.helpers.logging_helper import log_warning
from modules.scenarios.gm_table.layout_store import GMTableLayoutStore
from modules.scenarios.gm_table.table_registry import get_table_name, normalize_table_id

MANIFEST_KEY = "gm_virtual_tables"


def _store_path(campaign_root: Path) -> Path:
    return Path(campaign_root).resolve() / GMTableLayoutStore.FILE_NAME


def _read_store(campaign_root: Path) -> dict[str, Any]:
    path = _store_path(campaign_root)
    if not path.exists() or not path.is_file():
        return {"tables": {}, "global": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_warning(
            f"Unable to load GM virtual tables from {path}: {exc}",
            func_name="cross_campaign_gm_tables._read_store",
        )
        return {"tables": {}, "global": {}}
    return payload if isinstance(payload, dict) else {"tables": {}, "global": {}}


def _write_store(campaign_root: Path, payload: dict[str, Any]) -> None:
    path = _store_path(campaign_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _table_names(payload: dict[str, Any]) -> dict[str, str]:
    global_settings = payload.get("global")
    if not isinstance(global_settings, dict):
        return {}
    names = global_settings.get("table_names")
    if not isinstance(names, dict):
        return {}
    return {
        normalize_table_id(key): str(value)
        for key, value in names.items()
        if str(value).strip()
    }


def load_gm_virtual_tables(campaign_root: Path) -> List[dict[str, Any]]:
    """Return GM table layouts as selectable records for the asset library."""
    payload = _read_store(campaign_root)
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        return []
    names = _table_names(payload)
    records: List[dict[str, Any]] = []
    for table_id, layout in sorted(tables.items()):
        normalized_id = normalize_table_id(table_id)
        if not isinstance(layout, dict):
            continue
        panel_count = (
            len(layout.get("panels") or [])
            if isinstance(layout.get("panels"), list)
            else 0
        )
        records.append(
            {
                "TableId": normalized_id,
                "Name": names.get(normalized_id) or get_table_name(normalized_id),
                "Summary": f"{panel_count} panel(s)",
                "Layout": copy.deepcopy(layout),
            }
        )
    return records


def export_gm_virtual_tables(
    campaign_root: Path, records: List[dict[str, Any]], temp_root: Path, manifest: dict
) -> None:
    """Write selected GM virtual table records to a bundle manifest."""
    if not records:
        return
    payload = {"tables": {}, "global": {"table_names": {}}}
    for record in records:
        table_id = normalize_table_id(
            record.get("TableId") or record.get("Name") or "table"
        )
        layout = record.get("Layout") if isinstance(record.get("Layout"), dict) else {}
        payload["tables"][table_id] = copy.deepcopy(layout)
        name = str(record.get("Name") or "").strip()
        if name and name != get_table_name(table_id):
            payload["global"]["table_names"][table_id] = name
    data_path = temp_root / "data" / "gm_virtual_tables.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest[MANIFEST_KEY] = {
        "count": len(payload["tables"]),
        "data_path": "data/gm_virtual_tables.json",
    }


def load_bundled_gm_virtual_tables(
    temp_root: Path, manifest: dict
) -> dict[str, Any] | None:
    section = manifest.get(MANIFEST_KEY)
    if not isinstance(section, dict):
        return None
    data_path = str(section.get("data_path") or "").strip()
    if not data_path:
        return None
    file_path = temp_root / data_path
    if not file_path.exists():
        return None
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_warning(
            f"Unable to parse bundled GM virtual tables {data_path}: {exc}",
            func_name="cross_campaign_gm_tables.load_bundled_gm_virtual_tables",
        )
        return None
    return payload if isinstance(payload, dict) else None


def merge_gm_virtual_tables(
    campaign_root: Path, bundled: dict[str, Any] | None, *, overwrite: bool
) -> dict[str, int]:
    summary = {
        "gm_virtual_tables_imported": 0,
        "gm_virtual_tables_updated": 0,
        "gm_virtual_tables_skipped": 0,
    }
    if not bundled:
        return summary
    incoming_tables = bundled.get("tables")
    if not isinstance(incoming_tables, dict):
        return summary
    current = _read_store(campaign_root)
    current_tables = current.setdefault("tables", {})
    if not isinstance(current_tables, dict):
        current_tables = {}
        current["tables"] = current_tables
    current_global = current.setdefault("global", {})
    if not isinstance(current_global, dict):
        current_global = {}
        current["global"] = current_global
    current_names = current_global.setdefault("table_names", {})
    if not isinstance(current_names, dict):
        current_names = {}
        current_global["table_names"] = current_names
    incoming_names = _table_names(bundled)
    changed = False
    for raw_table_id, layout in incoming_tables.items():
        table_id = normalize_table_id(raw_table_id)
        if not isinstance(layout, dict):
            continue
        exists = table_id in current_tables
        if exists and not overwrite:
            summary["gm_virtual_tables_skipped"] += 1
            continue
        current_tables[table_id] = copy.deepcopy(layout)
        if table_id in incoming_names:
            current_names[table_id] = incoming_names[table_id]
        if exists:
            summary["gm_virtual_tables_updated"] += 1
        else:
            summary["gm_virtual_tables_imported"] += 1
        changed = True
    if changed:
        _write_store(campaign_root, current)
    return summary
