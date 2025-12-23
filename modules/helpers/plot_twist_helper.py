from __future__ import annotations

from typing import Optional

from modules.dice import dice_engine
from modules.helpers.logging_helper import log_exception, log_info, log_module_import
from modules.helpers.random_table_loader import RandomTableLoader


PLOT_TWIST_TABLE_ID = "universal_plot_twists"


def load_plot_twists_table(table_id: str = PLOT_TWIST_TABLE_ID) -> Optional[dict]:
    loader = RandomTableLoader(RandomTableLoader.default_data_path())
    data = loader.load()
    return data.get("tables", {}).get(table_id)


def _match_entry(table: dict, value: int) -> dict:
    for entry in table.get("entries", []):
        if entry.get("min", 0) <= value <= entry.get("max", 0):
            return entry
    return table.get("entries", [{}])[0] if table.get("entries") else {"result": "(no entries)"}


def roll_plot_twist(table_id: str = PLOT_TWIST_TABLE_ID) -> Optional[dict]:
    table = load_plot_twists_table(table_id)
    if not table:
        log_info("Plot twist table not found.", func_name="roll_plot_twist")
        return None
    try:
        roll = dice_engine.roll_formula(table.get("dice", "1d20"))
    except Exception as exc:
        log_exception(exc, func_name="roll_plot_twist")
        return None

    entry = _match_entry(table, roll.total)
    return {
        "table": table.get("title"),
        "roll": roll.total,
        "result": entry.get("result"),
        "entry": entry,
        "dice": table.get("dice"),
        "description": table.get("description") or "",
    }


log_module_import(__name__)

__all__ = ["PLOT_TWIST_TABLE_ID", "load_plot_twists_table", "roll_plot_twist"]
